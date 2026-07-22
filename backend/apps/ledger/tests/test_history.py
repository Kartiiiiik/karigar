import datetime
from decimal import Decimal

import pytest

from apps.ledger.models import Direction, GoldEntry

GOLD = "/api/v1/gold-entries/"


@pytest.mark.django_db
def test_gold_entry_history_records_edit(api, manager, karigar_profile):
    c = api(manager)
    created = c.post_form(GOLD, {
        "karigar": karigar_profile.id, "direction": "dr",
        "gross_weight_g": "10.000", "carat": 24, "entry_date": "2024-03-01",
    })
    entry_id = created.json()["id"]

    # Edit gross -> new history row + recomputed net.
    r = c.patch(f"{GOLD}{entry_id}/", {"gross_weight_g": "12.000"})
    assert r.status_code == 200, r.content

    hist = c.get(f"{GOLD}{entry_id}/history/")
    assert hist.status_code == 200
    rows = hist.json()
    assert len(rows) >= 2
    updates = [h for h in rows if h["type"] == "updated"]
    assert updates
    fields = [ch["field"] for ch in updates[0]["changes"]]
    assert "gross_weight_g" in fields or "net_weight_g" in fields


@pytest.mark.django_db
def test_karigar_history_scoped(api, karigar_user, karigar_profile, owner):
    entry = GoldEntry.objects.create(
        shop=karigar_profile.shop, karigar=karigar_profile, direction=Direction.DR,
        gross_weight_g=Decimal("10.000"), carat=24,
        entry_date=datetime.date(2024, 3, 1), created_by=owner,
    )
    resp = api(karigar_user).get(f"{GOLD}{entry.id}/history/")
    # Their own entry's history is readable.
    assert resp.status_code == 200
