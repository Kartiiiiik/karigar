from datetime import datetime

from django.core.validators import validate_email
from ninja import Schema
from pydantic import field_validator


class BackupConfigSchema(Schema):
    recipient_emails: str = ""
    frequency: str = "off"
    enabled: bool = False
    last_run_at: datetime | None = None


class BackupConfigPatch(Schema):
    recipient_emails: str | None = None
    frequency: str | None = None
    enabled: bool | None = None

    @field_validator("recipient_emails")
    @classmethod
    def _validate_emails(cls, value):
        if value is None:
            return value
        emails = [e.strip() for e in value.split(",") if e.strip()]
        for e in emails:
            validate_email(e)
        return ", ".join(emails)


class BackupLogOut(Schema):
    id: int
    status: str
    triggered_by: str
    filename: str = ""
    message: str = ""
    created_at: datetime


class BackupLogPage(Schema):
    results: list[BackupLogOut]
    count: int
