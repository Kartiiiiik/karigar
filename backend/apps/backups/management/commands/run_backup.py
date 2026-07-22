"""`python manage.py run_backup` — dump, encrypt and write to destinations.

Runs for every shop (single-shop MVP) or a specific one via --shop. Intended to
be triggered by Celery Beat, cron, or Windows Task Scheduler.
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import Shop
from apps.backups import service


class Command(BaseCommand):
    help = "Run an encrypted backup to the configured destinations."

    def add_arguments(self, parser):
        parser.add_argument("--shop", type=int, default=None, help="Shop id (default: all).")
        parser.add_argument("--source", default="manual", help="Manifest source tag.")

    def handle(self, *args, **opts):
        shops = Shop.objects.all()
        if opts["shop"]:
            shops = shops.filter(pk=opts["shop"])
        for shop in shops:
            try:
                m = service.run_backup(shop, source=opts["source"])
                dest = m["destinations"]
                self.stdout.write(self.style.SUCCESS(
                    f"{shop}: {m['filename']} "
                    f"(primary={dest['primary']}, secondary={dest['secondary']})"
                ))
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"{shop}: backup failed — {exc}"))
