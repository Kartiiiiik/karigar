import pytest

from apps.backups import service
from apps.backups.crypto import decrypt_bytes, encrypt_bytes
from apps.backups.models import BackupConfig

FAKE_DUMP = b"PGDMP" + b"\x00fake custom-format archive body"


@pytest.fixture
def shop_owner(db):
    from apps.accounts.models import Role, Shop, User

    shop = Shop.objects.create(name="Backup Shop")
    owner = User(username="o", role=Role.OWNER, shop=shop, is_staff=True, is_superuser=True)
    owner.set_password("Karigar@123")
    owner.save()
    return shop, owner


@pytest.fixture
def configured(shop_owner, tmp_path):
    shop, owner = shop_owner
    primary = tmp_path / "primary"
    secondary = tmp_path / "secondary"
    primary.mkdir()
    # secondary intentionally NOT created -> best-effort skip path exercised.
    BackupConfig.objects.create(
        shop=shop, primary_path=str(primary), secondary_path=str(secondary / "missing")
    )
    return shop, owner, primary, secondary


def test_encrypt_decrypt_roundtrip():
    token = encrypt_bytes(FAKE_DUMP)
    assert token != FAKE_DUMP
    assert decrypt_bytes(token) == FAKE_DUMP


def test_pgdump_magic():
    assert service.looks_like_pgdump(FAKE_DUMP)
    assert not service.looks_like_pgdump(b"not a dump")


@pytest.mark.django_db
def test_ingest_plain_dump_stores_encrypted_and_lists(configured):
    shop, owner, primary, secondary = configured
    manifest = service.ingest_upload(shop, FAKE_DUMP, already_encrypted=False)

    # File on primary is encrypted (not the plaintext) + manifest present.
    stored = (primary / manifest["filename"]).read_bytes()
    assert stored != FAKE_DUMP and decrypt_bytes(stored) == FAKE_DUMP
    assert (primary / (manifest["filename"] + ".manifest.json")).exists()

    # Listing comes from the manifest on disk (not the DB).
    items = service.list_backups(shop)
    assert len(items) == 1
    assert items[0]["source"] == "manual_upload"
    assert items[0]["destinations"]["primary"] is True
    assert items[0]["destinations"]["secondary"] is False  # drive not attached


@pytest.mark.django_db
def test_ingest_rejects_non_pgdump(configured):
    shop, *_ = configured
    with pytest.raises(RuntimeError):
        service.ingest_upload(shop, b"garbage file", already_encrypted=False)


@pytest.mark.django_db
def test_upload_endpoint(api, configured):
    from django.core.files.uploadedfile import SimpleUploadedFile

    shop, owner, primary, _ = configured
    f = SimpleUploadedFile("db.dump", FAKE_DUMP, content_type="application/octet-stream")
    resp = api(owner).client.post(
        "/api/v1/backups/upload/",
        {"file": f, "encrypted": "false"},
        **api(owner).headers,
    )
    assert resp.status_code == 200, resp.content
    assert service.list_backups(shop)[0]["source"] == "manual_upload"


@pytest.mark.django_db
def test_restore_guarded(api, configured):
    shop, owner, *_ = configured
    from apps.accounts.models import Role, User

    manager = User(username="m", role=Role.MANAGER, shop=shop)
    manager.set_password("Karigar@123")
    manager.save()

    # Manager cannot restore.
    assert api(manager).post("/api/v1/backups/restore/",
                             {"filename": "x", "confirm": "RESTORE", "password": "Karigar@123"}).status_code == 403
    # Owner, wrong confirmation phrase.
    assert api(owner).post("/api/v1/backups/restore/",
                           {"filename": "x", "confirm": "nope", "password": "Karigar@123"}).status_code == 400
    # Owner, wrong password (re-auth fails).
    assert api(owner).post("/api/v1/backups/restore/",
                           {"filename": "x", "confirm": "RESTORE", "password": "wrong"}).status_code == 403
