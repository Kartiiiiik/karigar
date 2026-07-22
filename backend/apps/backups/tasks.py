"""Celery tasks for backups.

``run_backup_task`` executes a single shop's backup off the request thread.
``run_scheduled_backups`` is invoked by Celery Beat and fans out to every shop
whose config is due, based on weekly/monthly frequency.
"""
import logging

from celery import shared_task
from django.utils import timezone

from apps.accounts.models import Shop

from .models import BackupConfig, BackupLog
from .services import run_backup

logger = logging.getLogger("apps.backups")


@shared_task
def run_backup_task(shop_id, triggered_by=BackupLog.Trigger.SCHEDULED):
    shop = Shop.objects.filter(pk=shop_id).first()
    if not shop:
        return "shop-not-found"
    log = run_backup(shop, triggered_by=triggered_by)
    return log.status


def _is_due(config, now):
    if not config.enabled or config.frequency == BackupConfig.Frequency.OFF:
        return False
    if config.last_run_at is None:
        return True
    delta = now - config.last_run_at
    if config.frequency == BackupConfig.Frequency.WEEKLY:
        return delta.days >= 7
    if config.frequency == BackupConfig.Frequency.MONTHLY:
        return delta.days >= 30
    return False


@shared_task
def run_scheduled_backups():
    """Beat entrypoint: run any config that is due. Runs daily; each config's
    own frequency gates whether it actually fires."""
    now = timezone.now()
    fired = 0
    for config in BackupConfig.objects.select_related("shop").all():
        if _is_due(config, now):
            run_backup_task.delay(config.shop_id, BackupLog.Trigger.SCHEDULED)
            fired += 1
    return f"queued {fired} backup(s)"
