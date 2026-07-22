from django.contrib import admin

from .models import BackupConfig, BackupLog


@admin.register(BackupConfig)
class BackupConfigAdmin(admin.ModelAdmin):
    list_display = ("shop", "frequency", "enabled", "last_run_at")


@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    list_display = ("shop", "status", "triggered_by", "created_at", "filename")
    list_filter = ("status", "triggered_by", "shop")
