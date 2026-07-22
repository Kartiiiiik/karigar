"""Build and email an encrypted backup package."""
import io
import logging
import secrets

import pyzipper
from django.core import management
from django.core.mail import EmailMessage
from django.utils import timezone

from apps.reports.exporters import to_excel
from apps.reports.services import build_cash_report, build_gold_report

from .models import BackupConfig, BackupLog

logger = logging.getLogger("apps.backups")


def _dump_json():
    """Full data dump (natural of the whole DB) as bytes."""
    buf = io.StringIO()
    management.call_command(
        "dumpdata",
        "--natural-foreign",
        "--natural-primary",
        "-e", "contenttypes",
        "-e", "auth.permission",
        "-e", "admin.logentry",
        "-e", "sessions.session",
        indent=2,
        stdout=buf,
    )
    return buf.getvalue().encode("utf-8")


def build_backup_zip(shop, password):
    """Return (filename, zip_bytes) for an AES-encrypted backup archive."""
    stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    filename = f"karigar-backup-{shop.pk}-{stamp}.zip"

    gold_xlsx = to_excel(build_gold_report(shop))
    cash_xlsx = to_excel(build_cash_report(shop))
    data_json = _dump_json()

    buf = io.BytesIO()
    with pyzipper.AESZipFile(
        buf, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.writestr("data.json", data_json)
        zf.writestr("gold-ledger.xlsx", gold_xlsx)
        zf.writestr("cash-ledger.xlsx", cash_xlsx)
    buf.seek(0)
    return filename, buf.read()


def run_backup(shop, triggered_by, recipients=None, password=None):
    """Generate + email a backup, logging the outcome. Never raises — returns
    the BackupLog so the caller (API/task) stays resilient if email fails."""
    config = BackupConfig.objects.filter(shop=shop).first()
    recipients = recipients or (config.recipients() if config else [])
    # A generated password is emailed separately in the body (email isn't a
    # fully secure channel — surfaced to the user in the UI).
    password = password or secrets.token_urlsafe(12)

    try:
        filename, content = build_backup_zip(shop, password)

        if recipients:
            msg = EmailMessage(
                subject=f"[Karigar] Backup for {shop.name}",
                body=(
                    f"Attached is an encrypted backup for {shop.name}.\n\n"
                    f"Zip password: {password}\n\n"
                    "Note: email is not a fully secure channel. Store this "
                    "archive and password safely and delete the email once saved."
                ),
                to=recipients,
            )
            msg.attach(filename, content, "application/zip")
            msg.send(fail_silently=False)

        if config:
            config.last_run_at = timezone.now()
            config.save(update_fields=["last_run_at"])

        return BackupLog.objects.create(
            shop=shop, status=BackupLog.Status.SUCCESS, triggered_by=triggered_by,
            filename=filename,
            message=(f"Emailed to {', '.join(recipients)}" if recipients else "Generated (no recipients configured)"),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Backup failed for shop %s", shop.pk)
        return BackupLog.objects.create(
            shop=shop, status=BackupLog.Status.FAILED, triggered_by=triggered_by,
            message=str(exc),
        )
