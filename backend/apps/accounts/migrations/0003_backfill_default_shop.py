"""Data migration: guarantee every non-superuser user belongs to a Shop.

Safe on existing data and idempotent:
  * Domain records (KarigarProfile, Ornament, Order, GoldEntry, CashEntry,
    AppSetting, Backup*, Bandaki*) already carry a NON-NULL ``shop`` FK, so
    none can be orphaned — nothing to backfill there.
  * Only ``User.shop`` is nullable (superusers legitimately have none). If any
    non-superuser somehow lacks a shop, attach it to the existing shop, or to a
    freshly created "Default Shop" when the database has none yet.

Running this on the current single-shop database is a no-op.
"""
from django.db import migrations


def backfill_default_shop(apps, schema_editor):
    Shop = apps.get_model("accounts", "Shop")
    User = apps.get_model("accounts", "User")

    orphans = User.objects.filter(is_superuser=False, shop__isnull=True)
    if not orphans.exists():
        return  # nothing to do — data is already shop-scoped

    shop = Shop.objects.order_by("id").first()
    if shop is None:
        shop = Shop.objects.create(name="Default Shop")
    orphans.update(shop=shop)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_appsetting_date_format"),
    ]

    operations = [
        # Reverse is a no-op: we never want to strip shops on rollback.
        migrations.RunPython(backfill_default_shop, migrations.RunPython.noop),
    ]
