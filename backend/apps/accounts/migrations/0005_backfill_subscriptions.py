"""Give every existing shop an active subscription so the new gate does not
lock out shops that pre-date the subscription feature.

Safe/idempotent: only creates a Subscription for shops that lack one. New end
date defaults to one year out from today (Asia/Kathmandu handled at runtime;
here we use the naive date, which is fine for a coarse one-year grant).
"""
import datetime

from django.db import migrations


def backfill_subscriptions(apps, schema_editor):
    Shop = apps.get_model("accounts", "Shop")
    Subscription = apps.get_model("accounts", "Subscription")

    today = datetime.date.today()
    end = today + datetime.timedelta(days=365)
    for shop in Shop.objects.filter(subscription__isnull=True):
        Subscription.objects.create(
            shop=shop,
            start_date=today,
            end_date=end,
            plan="Initial grant",
            notes="Auto-created for a pre-existing shop by data migration.",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_subscription"),
    ]

    operations = [
        migrations.RunPython(backfill_subscriptions, migrations.RunPython.noop),
    ]
