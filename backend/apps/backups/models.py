"""Backup configuration and restore audit.

The list of available backups is NOT stored here — it is read from the storage
destinations' manifest files, so it survives total loss of this database. These
models only hold the schedule/destination config and an audit trail of restores.
"""
from django.db import models

from apps.common.models import TimeStampedModel


class BackupConfig(TimeStampedModel):
    class Frequency(models.TextChoices):
        OFF = "off", "Off"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    shop = models.OneToOneField("accounts.Shop", on_delete=models.CASCADE, related_name="backup_config")
    # Destination paths as the operator types them (Windows-style allowed); the
    # backend resolves them to the container's bind-mounted folders.
    primary_path = models.CharField(max_length=500, blank=True)
    secondary_path = models.CharField(max_length=500, blank=True)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.OFF)
    enabled = models.BooleanField(default=False)
    last_run_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Backup config for {self.shop} ({self.frequency})"


class RestoreAudit(TimeStampedModel):
    """Records every restore attempt — matters for accounting data."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    shop = models.ForeignKey("accounts.Shop", on_delete=models.CASCADE, related_name="restore_audits")
    performed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    backup_filename = models.CharField(max_length=255)
    safety_backup_filename = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Restore {self.backup_filename} @ {self.created_at:%Y-%m-%d %H:%M} ({self.status})"
