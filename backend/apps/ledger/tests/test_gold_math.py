import datetime
from decimal import Decimal

import pytest

from apps.ledger.models import Direction, GoldEntry, compute_net_weight


@pytest.mark.parametrize(
    "gross,carat,expected",
    [
        ("24.000", 24, "24.000"),   # 24kt -> unchanged
        ("24.000", 22, "22.000"),   # 24 * 22/24 = 22
        ("10.000", 22, "9.167"),    # 10 * 22/24 = 9.1666.. -> 9.167
        ("0.001", 24, "0.001"),
    ],
)
def test_compute_net_weight(gross, carat, expected):
    assert compute_net_weight(Decimal(gross), carat) == Decimal(expected)


@pytest.mark.django_db
def test_net_weight_stored_and_recomputed_on_edit(shop, karigar_profile, owner):
    entry = GoldEntry.objects.create(
        shop=shop, karigar=karigar_profile, direction=Direction.DR,
        gross_weight_g=Decimal("12.000"), carat=22,
        entry_date=datetime.date(2024, 3, 1), created_by=owner,
    )
    assert entry.net_weight_g == Decimal("11.000")  # 12 * 22/24

    # Editing carat recomputes.
    entry.carat = 24
    entry.save()
    entry.refresh_from_db()
    assert entry.net_weight_g == Decimal("12.000")


@pytest.mark.django_db
def test_gold_balance_signed_dr_cr(shop, karigar_profile, owner):
    # opening 5.000 Dr
    GoldEntry.objects.create(
        shop=shop, karigar=karigar_profile, direction=Direction.DR,
        gross_weight_g=Decimal("20.000"), carat=24,
        entry_date=datetime.date(2024, 3, 1), created_by=owner,
    )  # +20
    GoldEntry.objects.create(
        shop=shop, karigar=karigar_profile, direction=Direction.CR,
        gross_weight_g=Decimal("18.000"), carat=24,
        entry_date=datetime.date(2024, 3, 2), created_by=owner,
    )  # -18
    # 5 + 20 - 18 = 7.000 (net Dr)
    assert karigar_profile.gold_balance() == Decimal("7.000")


@pytest.mark.django_db
def test_cash_balance_signed_dr_cr(shop, karigar_profile, owner):
    from apps.ledger.models import CashEntry

    CashEntry.objects.create(
        shop=shop, karigar=karigar_profile, direction=Direction.DR,
        amount_npr=Decimal("5000.00"), entry_date=datetime.date(2024, 3, 1),
        created_by=owner,
    )
    CashEntry.objects.create(
        shop=shop, karigar=karigar_profile, direction=Direction.CR,
        amount_npr=Decimal("2000.00"), entry_date=datetime.date(2024, 3, 2),
        created_by=owner,
    )
    # 0 + 5000 - 2000 = 3000 (net Dr)
    assert karigar_profile.cash_balance() == Decimal("3000.00")


@pytest.mark.django_db
def test_order_wastage(shop, karigar_profile, ornament, owner):
    from apps.ledger.models import Order

    order = Order.objects.create(shop=shop, karigar=karigar_profile, created_by=owner)
    GoldEntry.objects.create(
        shop=shop, order=order, karigar=karigar_profile, direction=Direction.DR,
        gross_weight_g=Decimal("20.000"), carat=24,
        entry_date=datetime.date(2024, 3, 1), created_by=owner,
    )
    GoldEntry.objects.create(
        shop=shop, order=order, karigar=karigar_profile, direction=Direction.CR,
        gross_weight_g=Decimal("19.500"), carat=24, ornament=ornament,
        entry_date=datetime.date(2024, 3, 5), created_by=owner,
    )
    assert order.net_issued() == Decimal("20.000")
    assert order.net_received() == Decimal("19.500")
    assert order.wastage() == Decimal("0.500")
