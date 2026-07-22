"""Celery tasks for backups."""
import logging

from celery import shared_task
from django.utils import timezone

from apps.accounts.models import Shop

from . import service
from .models import BackupConfig

logger = logging.getLogger("apps.backups")


@shared_task
def run_backup_task(shop_id, source="scheduled"):
    shop = Shop.objects.filter(pk=shop_id).first()
    if not shop:
        return "shop-not-found"
    try:
        manifest = service.run_backup(shop, source=source)
        return manifest["filename"]
    except Exception as exc:  # noqa: BLE001
        logger.exception("Backup failed for shop %s", shop_id)
        return f"failed: {exc}"


def _is_due(config, now):
    if not config.enabled or config.frequency == BackupConfig.Frequency.OFF:
        return False
    if config.last_run_at is None:
        return True
    days = (now - config.last_run_at).days
    return {
        BackupConfig.Frequency.DAILY: days >= 1,
        BackupConfig.Frequency.WEEKLY: days >= 7,
        BackupConfig.Frequency.MONTHLY: days >= 30,
    }.get(config.frequency, False)


@shared_task
def run_scheduled_backups():
    """Beat entrypoint (runs daily); each config's own frequency gates it."""
    now = timezone.now()
    fired = 0
    for config in BackupConfig.objects.select_related("shop").all():
        if _is_due(config, now):
            run_backup_task.delay(config.shop_id, "scheduled")
            fired += 1
    return f"queued {fired} backup(s)"
