"""Archiving ledger entries.

The load-bearing test is ``test_archived_gold_entry_disappears_from_every_figure``.
An archived entry that still counts towards *one* forgotten aggregate is worse
than no archive at all — it produces a balance nobody can explain. That test
walks every figure the app derives from gold entries in a single pass, so an
aggregate added later has to be added to it too.
"""
import datetime
from decimal import Decimal

import pytest

from apps.ledger.models import CashEntry, Direction, GoldEntry

pytestmark = pytest.mark.django_db

TODAY = datetime.date(2026, 1, 15)


def gold(shop, karigar, direction, grams="10.000", carat=24, order_number="", ornament=None):
    return GoldEntry.objects.create(
        shop=shop, order_number=order_number, karigar=karigar, direction=direction,
        gross_weight_g=Decimal(grams), carat=carat, entry_date=TODAY, ornament=ornament,
    )


# ===========================================================================
# The exhaustive one
# ===========================================================================
def test_archived_gold_entry_disappears_from_every_figure(
    api, owner, shop, ornament, karigar_profile
):
    gold(shop, karigar_profile, Direction.DR, "20.000", order_number="ORD-1")
    receipt = gold(shop, karigar_profile, Direction.CR, "19.000",
                   order_number="ORD-1", ornament=ornament)
    opening = karigar_profile.opening_gold_g  # 5.000

    # --- with the receipt live -------------------------------------------
    assert karigar_profile.gold_balance() == opening + Decimal("1.000")

    client = api(owner)
    assert client.get("/api/v1/gold-entries/").json()["count"] == 2
    assert client.get("/api/v1/gold-entries/summary/").json()["total_cr"] == "19.000"
    assert client.get("/api/v1/karigars/").json()["results"][0]["gold_balance"] == "6.000"
    # The order number filter is a plain text match on the entries.
    assert client.get("/api/v1/gold-entries/", {"order_number": "ORD-1"}).json()["count"] == 2

    # --- archive it -------------------------------------------------------
    r = client.post(f"/api/v1/gold-entries/{receipt.id}/archive/", {"reason": "Keyed twice"})
    assert r.status_code == 200

    karigar_profile.refresh_from_db()

    # …and it must be gone from all of them.
    assert karigar_profile.gold_balance() == opening + Decimal("20.000")
    assert client.get("/api/v1/gold-entries/").json()["count"] == 1
    assert client.get("/api/v1/gold-entries/summary/").json()["total_cr"] == "0"
    assert client.get("/api/v1/karigars/").json()["results"][0]["gold_balance"] == "25.000"
    assert client.get("/api/v1/gold-entries/", {"order_number": "ORD-1"}).json()["count"] == 1

    # …and out of the report export.
    from apps.reports.services import build_gold_report

    assert len(build_gold_report(shop)["rows"]) == 1


def test_archived_cash_entry_leaves_the_balance(api, owner, shop, karigar_profile):
    entry = CashEntry.objects.create(
        shop=shop, karigar=karigar_profile, direction=Direction.DR,
        amount_npr=Decimal("5000.00"), entry_date=TODAY,
    )
    assert karigar_profile.cash_balance() == Decimal("5000.00")

    api(owner).post(f"/api/v1/cash-entries/{entry.id}/archive/", {"reason": "Duplicate"})
    assert karigar_profile.cash_balance() == Decimal("0.00")
    assert api(owner).get("/api/v1/cash-entries/").json()["count"] == 0
    assert api(owner).get("/api/v1/cash-entries/summary/").json()["total_dr"] == "0"

    from apps.reports.services import build_cash_report

    assert len(build_cash_report(shop)["rows"]) == 0


# ===========================================================================
# Archive / restore round trip
# ===========================================================================
def test_archive_records_who_and_why(api, owner, shop, karigar_profile):
    entry = gold(shop, karigar_profile, Direction.DR)
    api(owner).post(f"/api/v1/gold-entries/{entry.id}/archive/", {"reason": "Wrong karigar"})

    listed = api(owner).get("/api/v1/gold-entries/", {"archived": "true"}).json()["results"]
    assert len(listed) == 1
    assert listed[0]["archive_reason"] == "Wrong karigar"
    assert listed[0]["archived_by"] == "owner"
    assert listed[0]["archived_at"] is not None


def test_restore_puts_the_entry_and_its_effect_back(api, owner, shop, karigar_profile):
    entry = gold(shop, karigar_profile, Direction.DR, "20.000")
    client = api(owner)
    client.post(f"/api/v1/gold-entries/{entry.id}/archive/", {})
    assert karigar_profile.gold_balance() == Decimal("5.000")

    r = client.post(f"/api/v1/gold-entries/{entry.id}/restore/")
    assert r.status_code == 200
    assert r.json()["archived_at"] is None
    assert r.json()["archive_reason"] == ""
    assert karigar_profile.gold_balance() == Decimal("25.000")
    assert client.get("/api/v1/gold-entries/").json()["count"] == 1


def test_archived_entries_leave_the_ledger_but_keep_their_trail(api, owner, shop, karigar_profile):
    entry = gold(shop, karigar_profile, Direction.DR)
    client = api(owner)
    client.post(f"/api/v1/gold-entries/{entry.id}/archive/", {})

    assert client.get("/api/v1/gold-entries/").json()["count"] == 0
    assert client.get("/api/v1/gold-entries/", {"archived": "true"}).json()["count"] == 1
    # An archived row is not editable in place — restore it first.
    assert client.get(f"/api/v1/gold-entries/{entry.id}/").status_code == 404
    assert client.patch(f"/api/v1/gold-entries/{entry.id}/", {"carat": 22}).status_code == 404
    # …but its audit trail stays reachable for the Archive page.
    assert client.get(f"/api/v1/gold-entries/{entry.id}/history/").status_code == 200


def test_ledger_filters_still_work_inside_the_archive(api, owner, shop, karigar_profile):
    a = gold(shop, karigar_profile, Direction.DR, "10.000")
    b = gold(shop, karigar_profile, Direction.CR, "8.000", ornament=None)
    client = api(owner)
    for e in (a, b):
        client.post(f"/api/v1/gold-entries/{e.id}/archive/", {})

    only_dr = client.get("/api/v1/gold-entries/", {"archived": "true", "direction": "dr"}).json()
    assert only_dr["count"] == 1
    assert only_dr["results"][0]["id"] == a.id


# ===========================================================================
# Impact preview
# ===========================================================================
def test_impact_preview_matches_what_archiving_actually_does(
    api, owner, shop, ornament, karigar_profile
):
    gold(shop, karigar_profile, Direction.DR, "20.000")
    receipt = gold(shop, karigar_profile, Direction.CR, "19.000", ornament=ornament)
    client = api(owner)

    preview = client.get(f"/api/v1/gold-entries/{receipt.id}/archive-impact/").json()
    assert preview["karigar_name"] == "Ram"
    assert preview["balance_before"] == "6.000"
    assert preview["balance_after"] == "25.000"
    # The order number is just a label on the entry — the preview says nothing
    # about it.
    assert "order_label" not in preview

    # The preview must not have left the archive applied.
    receipt.refresh_from_db()
    assert receipt.archived_at is None
    assert client.get("/api/v1/gold-entries/").json()["count"] == 2

    # Now do it for real, and check the preview told the truth.
    client.post(f"/api/v1/gold-entries/{receipt.id}/archive/", {})
    assert str(karigar_profile.gold_balance()) == preview["balance_after"]


def test_impact_preview_for_a_standalone_entry(api, owner, shop, karigar_profile):
    entry = gold(shop, karigar_profile, Direction.DR, "3.000")
    preview = api(owner).get(f"/api/v1/gold-entries/{entry.id}/archive-impact/").json()
    assert preview["balance_before"] == "8.000"
    assert preview["balance_after"] == "5.000"


def test_cash_impact_preview(api, owner, shop, karigar_profile):
    entry = CashEntry.objects.create(
        shop=shop, karigar=karigar_profile, direction=Direction.DR,
        amount_npr=Decimal("1500.00"), entry_date=TODAY,
    )
    preview = api(owner).get(f"/api/v1/cash-entries/{entry.id}/archive-impact/").json()
    assert preview["entry_label"] == "Debit NPR 1500.00"
    assert preview["balance_before"] == "1500.00"
    assert preview["balance_after"] == "0.00"


# ===========================================================================
# Permissions
# ===========================================================================
def test_only_the_owner_can_permanently_delete(api, owner, manager, shop, karigar_profile):
    entry = gold(shop, karigar_profile, Direction.DR)
    api(owner).post(f"/api/v1/gold-entries/{entry.id}/archive/", {})

    assert api(manager).delete(f"/api/v1/gold-entries/{entry.id}/").status_code == 403
    assert GoldEntry.all_objects.filter(pk=entry.id).exists()

    assert api(owner).delete(f"/api/v1/gold-entries/{entry.id}/").status_code == 204
    assert not GoldEntry.all_objects.filter(pk=entry.id).exists()


def test_a_live_entry_cannot_be_deleted_without_archiving_first(api, owner, shop, karigar_profile):
    entry = gold(shop, karigar_profile, Direction.DR)
    r = api(owner).delete(f"/api/v1/gold-entries/{entry.id}/")
    assert r.status_code == 400
    assert "Archive the entry first" in r.json()["error"]["message"]
    assert GoldEntry.all_objects.filter(pk=entry.id).exists()


def test_a_manager_can_archive_and_restore(api, manager, shop, karigar_profile):
    entry = gold(shop, karigar_profile, Direction.DR)
    assert api(manager).post(f"/api/v1/gold-entries/{entry.id}/archive/", {}).status_code == 200
    assert api(manager).post(f"/api/v1/gold-entries/{entry.id}/restore/").status_code == 200


def test_karigars_cannot_archive_or_delete(
    api, owner, karigar_user, karigar_profile, shop
):
    entry = gold(shop, karigar_profile, Direction.DR)
    assert api(karigar_user).post(
        f"/api/v1/gold-entries/{entry.id}/archive/", {}
    ).status_code == 403

    api(owner).post(f"/api/v1/gold-entries/{entry.id}/archive/", {})
    # A karigar's own ledger no longer shows it…
    assert api(karigar_user).get("/api/v1/gold-entries/").json()["count"] == 0
    assert api(karigar_user).delete(f"/api/v1/gold-entries/{entry.id}/").status_code == 403


def test_archive_is_shop_scoped(api, owner, other_shop):
    from apps.accounts.models import Role, User
    from apps.ledger.models import KarigarProfile

    their_user = User(username="theirs", role=Role.KARIGAR, shop=other_shop, full_name="Theirs")
    their_user.set_password("x")
    their_user.save()
    their_karigar = KarigarProfile.objects.create(
        user=their_user, shop=other_shop, full_name="Theirs"
    )
    theirs = gold(other_shop, their_karigar, Direction.DR, "1.000")

    client = api(owner)
    assert client.post(f"/api/v1/gold-entries/{theirs.id}/archive/", {}).status_code == 404
    assert client.post(f"/api/v1/gold-entries/{theirs.id}/restore/").status_code == 404
    assert client.get(f"/api/v1/gold-entries/{theirs.id}/archive-impact/").status_code == 404
    assert client.delete(f"/api/v1/gold-entries/{theirs.id}/").status_code == 404
