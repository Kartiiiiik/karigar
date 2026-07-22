import datetime
import io

import pytest
import pyzipper
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import Role, Shop, User
from apps.backups.models import BackupConfig, BackupLog
from apps.backups.services import build_backup_zip, run_backup
from apps.backups.tasks import _is_due


@pytest.fixture
def shop_owner(db):
    shop = Shop.objects.create(name="Backup Shop")
    owner = User(username="o", role=Role.OWNER, shop=shop, is_staff=True, is_superuser=True)
    owner.set_password("Karigar@123")
    owner.save()
    return shop, owner


@pytest.mark.django_db
def test_build_zip_is_aes_encrypted(shop_owner):
    shop, _ = shop_owner
    filename, content = build_backup_zip(shop, "secret123")
    assert filename.endswith(".zip")
    # Correct password reads the members.
    with pyzipper.AESZipFile(io.BytesIO(content)) as zf:
        zf.setpassword(b"secret123")
        names = zf.namelist()
        assert "data.json" in names and "gold-ledger.xlsx" in names and "cash-ledger.xlsx" in names
        assert zf.read("data.json")  # decrypts
    # Wrong password fails.
    with pyzipper.AESZipFile(io.BytesIO(content)) as zf:
        zf.setpassword(b"wrong")
        with pytest.raises(RuntimeError):
            zf.read("data.json")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_run_backup_emails_and_logs(shop_owner):
    shop, _ = shop_owner
    BackupConfig.objects.create(shop=shop, recipient_emails="a@b.com", enabled=True)
    log = run_backup(shop, triggered_by=BackupLog.Trigger.MANUAL)
    assert log.status == BackupLog.Status.SUCCESS
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["a@b.com"]
    assert mail.outbox[0].attachments  # the zip


@pytest.mark.django_db
def test_run_backup_now_endpoint(api, shop_owner):
    shop, owner = shop_owner
    resp = api(owner).post("/api/v1/backups/run/")
    assert resp.status_code == 200
    assert BackupLog.objects.filter(shop=shop).exists()


@pytest.mark.django_db
def test_scheduled_due_logic(shop_owner):
    shop, _ = shop_owner
    now = timezone.now()
    weekly = BackupConfig(shop=shop, frequency=BackupConfig.Frequency.WEEKLY, enabled=True, last_run_at=None)
    assert _is_due(weekly, now) is True
    weekly.last_run_at = now - datetime.timedelta(days=3)
    assert _is_due(weekly, now) is False
    weekly.last_run_at = now - datetime.timedelta(days=8)
    assert _is_due(weekly, now) is True
    off = BackupConfig(shop=shop, frequency=BackupConfig.Frequency.OFF, enabled=True)
    assert _is_due(off, now) is False
