"""Backup API: schedule config, run-now, and run logs. Owner + manager."""

from ninja import Router
from ninja.pagination import paginate

from apps.common.auth import require_staff
from apps.common.pagination import DefaultPagination

from .models import BackupConfig, BackupLog
from .schemas import BackupConfigPatch, BackupConfigSchema, BackupLogOut
from .tasks import run_backup_task

router = Router(tags=["backups"])


def _config(request):
    config, _ = BackupConfig.objects.get_or_create(shop=request.auth.shop)
    return config


@router.get("/backups/config/", response=BackupConfigSchema)
def get_config(request):
    require_staff(request)
    return _config(request)


@router.patch("/backups/config/", response=BackupConfigSchema)
def update_config(request, payload: BackupConfigPatch):
    require_staff(request)
    config = _config(request)
    for f, v in payload.dict(exclude_unset=True).items():
        setattr(config, f, v)
    config.save()
    return config


@router.get("/backups/logs/", response=list[BackupLogOut])
@paginate(DefaultPagination)
def list_logs(request):
    require_staff(request)
    return BackupLog.objects.filter(shop=request.auth.shop)


@router.post("/backups/run/", response={200: dict})
def run_now(request):
    """Manual backup. Runs via Celery when a broker is available; otherwise
    degrades to an inline run so the app stays usable if Redis/Celery is down."""
    require_staff(request)
    shop = request.auth.shop
    try:
        run_backup_task.delay(shop.id, BackupLog.Trigger.MANUAL)
        return 200, {"detail": "Backup started."}
    except Exception:
        run_backup_task(shop.id, BackupLog.Trigger.MANUAL)
        return 200, {"detail": "Backup completed (ran inline)."}
