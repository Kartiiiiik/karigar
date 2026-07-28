"""Replace the Order foreign key on ledger entries with a plain text label.

An order is now just a number written on the shop's paperwork: staff type it on
an entry if there is one, and nothing in the app is derived from it. With no
entry pointing at it, the ``Order`` model had nothing left to do, so it goes.

The operation order matters. Django's autodetector wanted to drop the foreign
keys *before* adding the text column, which would have thrown away every
existing order number. Here the column is added first and the numbers copied
across, so no data is lost.
"""
from django.db import migrations, models

ORDER_NUMBER = models.CharField(blank=True, db_index=True, max_length=60)


def copy_order_numbers(apps, schema_editor):
    """Carry each entry's linked order number onto the entry itself."""
    for name in ("GoldEntry", "CashEntry"):
        model = apps.get_model("ledger", name)
        for entry in model.objects.filter(order__isnull=False).select_related("order").iterator():
            number = entry.order.order_number or f"Order #{entry.order_id}"
            model.objects.filter(pk=entry.pk).update(order_number=number[:60])


def noop(apps, schema_editor):
    """Reverse is a no-op: re-creating Order rows from bare text would be
    inventing records. The numbers themselves stay on the entries."""


class Migration(migrations.Migration):
    dependencies = [("ledger", "0004_entry_archive")]

    operations = [
        # 1. New column on both the live and historical tables.
        migrations.AddField(model_name="goldentry", name="order_number", field=ORDER_NUMBER),
        migrations.AddField(model_name="cashentry", name="order_number", field=ORDER_NUMBER),
        migrations.AddField(
            model_name="historicalgoldentry", name="order_number", field=ORDER_NUMBER
        ),
        migrations.AddField(
            model_name="historicalcashentry", name="order_number", field=ORDER_NUMBER
        ),
        # 2. Copy the numbers across while the links still exist.
        migrations.RunPython(copy_order_numbers, noop),
        # 3. Drop the links.
        migrations.RemoveField(model_name="goldentry", name="order"),
        migrations.RemoveField(model_name="cashentry", name="order"),
        migrations.RemoveField(model_name="historicalgoldentry", name="order"),
        migrations.RemoveField(model_name="historicalcashentry", name="order"),
        # 4. And the model nothing points at any more.
        migrations.RemoveField(model_name="order", name="created_by"),
        migrations.RemoveField(model_name="order", name="karigar"),
        migrations.RemoveField(model_name="order", name="ornament"),
        migrations.RemoveField(model_name="order", name="shop"),
        migrations.RemoveField(model_name="order", name="updated_by"),
        migrations.DeleteModel(name="HistoricalOrder"),
        migrations.DeleteModel(name="Order"),
    ]
