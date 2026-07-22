"""Backup API: config, run, storage-sourced listing, manual upload, restore.

Listing reads manifest files from the storage destinations (not the DB), so it
keeps working after the database/volume is wiped. Restore is owner-only and
re-authenticated + typed-confirmed given it is destructive.
"""
from ninja import File, Form, Router
from ninja.errors import HttpError
from ninja.files import UploadedFile

from apps.common.auth import require_owner, require_staff

from . import service
from .models import BackupConfig, RestoreAudit
from .schemas import (
    BackupConfigPatch,
    BackupConfigSchema,
    BackupItemOut,
    RestoreAuditOut,
    RestoreIn,
)

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


@router.get("/backups/", response=list[BackupItemOut])
def list_backups(request):
    """Recent backups, sourced from destination manifests (survives DB loss)."""
    require_staff(request)
    return service.list_backups(request.auth.shop)


@router.post("/backups/run/", response={200: dict})
def run_now(request):
    require_staff(request)
    from .tasks import run_backup_task

    shop = request.auth.shop
    try:
        run_backup_task.delay(shop.id, "manual")
        return 200, {"detail": "Backup started."}
    except Exception:
        # Broker down -> run inline so the app stays usable.
        manifest = service.run_backup(shop, source="manual")
        return 200, {"detail": "Backup completed.", "filename": manifest["filename"]}


@router.post("/backups/upload/", response={200: dict})
def upload_backup(request, file: UploadedFile = File(...), encrypted: bool = Form(False)):
    require_staff(request)
    raw = file.read()
    already_encrypted = encrypted or file.name.endswith(".enc")
    try:
        manifest = service.ingest_upload(request.auth.shop, raw, already_encrypted)
    except RuntimeError as exc:
        raise HttpError(400, str(exc)) from exc
    return 200, {"detail": "Backup uploaded.", "filename": manifest["filename"]}


@router.get("/backups/audits/", response=list[RestoreAuditOut])
def list_audits(request):
    require_staff(request)
    return RestoreAudit.objects.filter(shop=request.auth.shop)[:50]


@router.post("/backups/restore/", response={200: dict})
def restore(request, payload: RestoreIn):
    # Owner-only + re-authentication + typed confirmation (destructive action).
    require_owner(request)
    if payload.confirm.strip().upper() != "RESTORE":
        raise HttpError(400, "Type RESTORE to confirm.")
    if not request.auth.check_password(payload.password):
        raise HttpError(403, "Re-authentication failed: incorrect password.")
    try:
        safety_name, audit = service.perform_restore(
            request.auth.shop, payload.filename, request.auth
        )
    except RuntimeError as exc:
        raise HttpError(400, str(exc)) from exc
    return 200, {
        "detail": "Restore complete.",
        "safety_backup": safety_name,
        "audit_id": audit.id,
    }
