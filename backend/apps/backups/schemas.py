from datetime import datetime
from typing import Any

from ninja import Schema


class BackupConfigSchema(Schema):
    primary_path: str = ""
    secondary_path: str = ""
    frequency: str = "off"
    enabled: bool = False
    last_run_at: datetime | None = None


class BackupConfigPatch(Schema):
    primary_path: str | None = None
    secondary_path: str | None = None
    frequency: str | None = None
    enabled: bool | None = None


class BackupItemOut(Schema):
    filename: str
    timestamp: str = ""
    size: int = 0
    checksum_sha256: str = ""
    source: str = ""
    app_sha: str = ""
    destinations: dict[str, Any] = {}


class RestoreIn(Schema):
    filename: str
    confirm: str        # must equal "RESTORE"
    password: str       # re-authentication


class RestoreAuditOut(Schema):
    id: int
    backup_filename: str
    safety_backup_filename: str = ""
    status: str
    message: str = ""
    performed_by: str | None = None
    created_at: datetime

    @staticmethod
    def resolve_performed_by(obj):
        return obj.performed_by.username if obj.performed_by_id else None
