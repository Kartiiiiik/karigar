"""Backup configuration and run log.

A backup packages a full JSON dump of the shop's data plus Excel exports of the
cash and gold ledgers into an AES-encrypted zip, emailed to the configured
recipients. Runs can be manual or scheduled (weekly/monthly via Celery Beat).
"""
from django.db import models

from apps.common.models import TimeStampedModel


class BackupConfig(TimeStampedModel):
    class Frequency(models.TextChoices):
        OFF = "off", "Off"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    shop = models.OneToOneField("accounts.Shop", on_delete=models.CASCADE, related_name="backup_config")
    # Comma-separated recipient list (kept simple; validated in the serializer).
    recipient_emails = models.TextField(blank=True, help_text="Comma-separated email addresses.")
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.OFF)
    enabled = models.BooleanField(default=False)
    last_run_at = models.DateTimeField(null=True, blank=True)

    def recipients(self):
        return [e.strip() for e in self.recipient_emails.split(",") if e.strip()]

    def __str__(self):
        return f"Backup config for {self.shop} ({self.frequency})"


class BackupLog(TimeStampedModel):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual"
        SCHEDULED = "scheduled", "Scheduled"

    shop = models.ForeignKey("accounts.Shop", on_delete=models.CASCADE, related_name="backup_logs")
    status = models.CharField(max_length=10, choices=Status.choices)
    triggered_by = models.CharField(max_length=10, choices=Trigger.choices)
    filename = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.status}"
