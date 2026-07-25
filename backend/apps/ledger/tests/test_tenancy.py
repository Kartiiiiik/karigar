"""Multi-shop tenant isolation.

A user in Shop A must never be able to read or write Shop B's data — not via
list endpoints, and not by guessing/altering record IDs (object-level checks).
Creates always attach the caller's own shop, regardless of any client input.
"""
import datetime
from decimal import Decimal

import pytest

from apps.accounts.models import Role, Shop, User
from apps.ledger.models import Direction, GoldEntry, KarigarProfile

KARIGARS = "/api/v1/karigars/"
GOLD = "/api/v1/gold-entries/"
CASH = "/api/v1/cash-entries/"


# --- Shop B fixtures (Shop A ones come from conftest: shop/owner/manager) -----
@pytest.fixture
def shop_b(db):
    return Shop.objects.create(name="Shop B")


@pytest.fixture
def manager_b(shop_b):
    u = User(username="manager_b", role=Role.MANAGER, shop=shop_b, full_name="Manager B")
    u.set_password("Karigar@123")
    u.save()
    return u


@pytest.fixture
def karigar_user_b(shop_b):
    u = User(username="karigar_b", role=Role.KARIGAR, shop=shop_b, full_name="Karigar B")
    u.set_password("Karigar@123")
    u.save()
    return u


@pytest.fixture
def karigar_profile_b(shop_b, karigar_user_b):
    return KarigarProfile.objects.create(
        user=karigar_user_b, shop=shop_b, full_name="Hari",
        opening_gold_g=Decimal("3.000"), opening_cash_npr=Decimal("0.00"),
        joined_date=datetime.date(2024, 1, 1),
    )


@pytest.fixture
def gold_b(shop_b, manager_b, karigar_profile_b):
    return GoldEntry.objects.create(
        shop=shop_b, karigar=karigar_profile_b, direction=Direction.DR,
        gross_weight_g=Decimal("10.000"), carat=24,
        entry_date=datetime.date(2024, 3, 1), created_by=manager_b,
    )


# --- List isolation -----------------------------------------------------------
@pytest.mark.django_db
def test_manager_list_karigars_excludes_other_shop(api, manager, karigar_profile, karigar_profile_b):
    resp = api(manager).get(KARIGARS)
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.json()["results"]]
    assert karigar_profile.id in ids
    assert karigar_profile_b.id not in ids


@pytest.mark.django_db
def test_manager_list_gold_excludes_other_shop(api, manager, gold_b):
    resp = api(manager).get(GOLD)
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.json()["results"]]
    assert gold_b.id not in ids


# --- Object-level isolation (guessing IDs) ------------------------------------
@pytest.mark.django_db
def test_manager_cannot_read_other_shop_karigar_by_id(api, manager, karigar_profile_b):
    resp = api(manager).get(f"{KARIGARS}{karigar_profile_b.id}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_manager_cannot_read_other_shop_gold_by_id(api, manager, gold_b):
    resp = api(manager).get(f"{GOLD}{gold_b.id}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_manager_cannot_patch_other_shop_gold_by_id(api, manager, gold_b):
    resp = api(manager).patch(f"{GOLD}{gold_b.id}/", {"remarks": "hacked"})
    assert resp.status_code == 404
    gold_b.refresh_from_db()
    assert gold_b.remarks != "hacked"


@pytest.mark.django_db
def test_manager_cannot_delete_other_shop_karigar_by_id(api, manager, karigar_profile_b):
    resp = api(manager).delete(f"{KARIGARS}{karigar_profile_b.id}/")
    assert resp.status_code == 404
    karigar_profile_b.refresh_from_db()
    assert karigar_profile_b.is_active is True


# --- Create attaches the caller's own shop ------------------------------------
@pytest.mark.django_db
def test_created_karigar_belongs_to_callers_shop(api, manager, shop):
    resp = api(manager).post_form(KARIGARS, {"full_name": "Fresh Karigar"})
    assert resp.status_code == 201, resp.content
    created = KarigarProfile.objects.get(id=resp.json()["id"])
    assert created.shop_id == shop.id


@pytest.mark.django_db
def test_manager_cannot_create_gold_for_other_shop_karigar(api, manager, karigar_profile_b):
    # Referencing another shop's karigar must be rejected (the karigar is
    # invisible outside its shop -> "Unknown karigar", HTTP 400) and no entry
    # may be created.
    resp = api(manager).post_form(GOLD, {
        "karigar": karigar_profile_b.id, "direction": "dr",
        "gross_weight_g": "5.000", "carat": 24, "entry_date": "2024-03-01",
    })
    assert resp.status_code in (400, 403, 404)
    assert not GoldEntry.objects.filter(karigar=karigar_profile_b).exists()
