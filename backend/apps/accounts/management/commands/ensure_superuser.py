"""Idempotently create the platform superuser from environment variables.

Run on container boot (see entrypoint.sh). The platform administrator is a
Django superuser who operates only through the admin panel and has NO shop, so
it is never subject to the subscription lock.

Reads:
    DJANGO_SUPERUSER_USERNAME   (required)
    DJANGO_SUPERUSER_PASSWORD   (required)
    DJANGO_SUPERUSER_EMAIL      (optional)

If the user already exists it is left untouched (a manual password change in
admin is never clobbered). Missing username/password -> skip silently.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the platform superuser from DJANGO_SUPERUSER_* env vars if absent."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL") or None

        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME/PASSWORD not set; skipping superuser bootstrap.")
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Superuser '{username}' already exists; leaving as-is.")
            return

        User.objects.create_superuser(username=username, password=password, email=email)
        self.stdout.write(self.style.SUCCESS(f"Created platform superuser '{username}'."))
