from django.contrib import admin

from .models import BackupConfig, RestoreAudit


@admin.register(BackupConfig)
class BackupConfigAdmin(admin.ModelAdmin):
    list_display = ("shop", "frequency", "enabled", "primary_path", "secondary_path", "last_run_at")


@admin.register(RestoreAudit)
class RestoreAuditAdmin(admin.ModelAdmin):
    list_display = ("shop", "backup_filename", "status", "performed_by", "created_at")
    list_filter = ("status", "shop")
    readonly_fields = ("shop", "performed_by", "backup_filename", "safety_backup_filename", "status", "message")
