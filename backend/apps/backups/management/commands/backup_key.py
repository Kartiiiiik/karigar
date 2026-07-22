"""`python manage.py backup_key` — print a fresh master encryption key to put
in BACKUP_ENCRYPTION_KEY (env / secrets manager). Never commit this value."""
from django.core.management.base import BaseCommand

from apps.backups.crypto import generate_key


class Command(BaseCommand):
    help = "Generate a backup master encryption key."

    def handle(self, *args, **opts):
        self.stdout.write(generate_key())
