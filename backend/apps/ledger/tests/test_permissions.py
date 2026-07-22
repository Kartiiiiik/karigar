"""Object-level scoping and role permissions, enforced at the API layer."""
import datetime
from decimal import Decimal

import pytest

from apps.ledger.models import Direction, GoldEntry

KARIGARS = "/api/v1/karigars/"
GOLD = "/api/v1/gold-entries/"
CASH = "/api/v1/cash-entries/"


@pytest.fixture
def gold_for(shop, owner):
    def _make(profile, direction=Direction.DR, gross="10.000", carat=24):
        return GoldEntry.objects.create(
            shop=shop, karigar=profile, direction=direction,
            gross_weight_g=Decimal(gross), carat=carat,
            entry_date=datetime.date(2024, 3, 1), created_by=owner,
        )
    return _make


@pytest.mark.django_db
def test_manager_can_create_karigar(api, manager):
    resp = api(manager).post_form(KARIGARS, {
        "username": "newk", "password": "Karigar@123", "full_name": "New Karigar",
    })
    assert resp.status_code == 201, resp.content
    from apps.accounts.models import User
    assert User.objects.get(username="newk").role == "karigar"


@pytest.mark.django_db
def test_karigar_autogenerates_credentials(api, manager):
    # No username/password supplied -> generated from the name; password returned.
    resp = api(manager).post_form(KARIGARS, {"full_name": "Ram Bahadur"})
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["username"] == "rambahadur"
    assert body["generated_password"]  # plaintext returned once
    from apps.accounts.models import User
    assert User.objects.get(username="rambahadur").check_password(body["generated_password"])


@pytest.mark.django_db
def test_gold_search_by_weight(api, manager, karigar_profile, gold_for):
    gold_for(karigar_profile, gross="12.000")
    gold_for(karigar_profile, gross="99.000")
    resp = api(manager).get(GOLD, {"search": "12", "karigar": karigar_profile.id})
    assert resp.status_code == 200
    rows = resp.json()["results"]
    assert len(rows) == 1
    assert rows[0]["gross_weight_g"] in ("12.000", 12.0, "12.0")


@pytest.mark.django_db
def test_gold_summary_totals(api, manager, karigar_profile, gold_for):
    gold_for(karigar_profile, direction=Direction.DR, gross="20.000")
    gold_for(karigar_profile, direction=Direction.CR, gross="8.000")
    resp = api(manager).get("/api/v1/gold-entries/summary/", {"karigar": karigar_profile.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert Decimal(body["total_dr"]) == Decimal("20.000")
    assert Decimal(body["total_cr"]) == Decimal("8.000")


@pytest.mark.django_db
def test_ornament_case_insensitive_uniqueness(api, manager):
    ORN = "/api/v1/ornaments/"
    assert api(manager).post(ORN, {"name": "Ring"}).status_code == 201
    dup = api(manager).post(ORN, {"name": "ring"})
    assert dup.status_code == 400


@pytest.mark.django_db
def test_karigar_cannot_list_karigars(api, karigar_user, karigar_profile):
    assert api(karigar_user).get(KARIGARS).status_code == 403


@pytest.mark.django_db
def test_karigar_sees_only_own_gold_entries(api, karigar_user, karigar_profile, other_karigar_profile, gold_for):
    mine = gold_for(karigar_profile)
    gold_for(other_karigar_profile)
    resp = api(karigar_user).get(GOLD)
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.json()["results"]]
    assert ids == [mine.id]


@pytest.mark.django_db
def test_karigar_cannot_create_gold_entry(api, karigar_user, karigar_profile):
    resp = api(karigar_user).post_form(GOLD, {
        "karigar": karigar_profile.id, "direction": "dr",
        "gross_weight_g": "10.000", "carat": 24, "entry_date": "2024-03-01",
    })
    assert resp.status_code == 403


@pytest.mark.django_db
def test_manager_creates_gold_entry_computes_net(api, manager, karigar_profile):
    resp = api(manager).post_form(GOLD, {
        "karigar": karigar_profile.id, "direction": "dr",
        "gross_weight_g": "12.000", "carat": 22, "entry_date": "2024-03-01",
    })
    assert resp.status_code == 201, resp.content
    assert Decimal(str(resp.json()["net_weight_g"])) == Decimal("11.000")


@pytest.mark.django_db
def test_gold_receive_requires_ornament(api, manager, karigar_profile):
    resp = api(manager).post_form(GOLD, {
        "karigar": karigar_profile.id, "direction": "cr",
        "gross_weight_g": "12.000", "carat": 22, "entry_date": "2024-03-01",
    })
    assert resp.status_code == 400


@pytest.mark.django_db
def test_karigar_self_view(api, karigar_user, karigar_profile):
    resp = api(karigar_user).get("/api/v1/me/karigar/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "Ram"
    assert body["gold_balance"] == "5.000"


@pytest.mark.django_db
def test_staff_has_no_self_view(api, manager):
    assert api(manager).get("/api/v1/me/karigar/").status_code == 404


@pytest.mark.django_db
def test_cash_entry_receive_reduces_balance(api, manager, karigar_profile):
    c = api(manager)
    c.post(CASH, {"karigar": karigar_profile.id, "direction": "dr", "amount_npr": "5000.00", "entry_date": "2024-03-01"})
    c.post(CASH, {"karigar": karigar_profile.id, "direction": "cr", "amount_npr": "2000.00", "entry_date": "2024-03-02"})
    assert karigar_profile.cash_balance() == Decimal("3000.00")


@pytest.mark.django_db
def test_soft_delete_karigar(api, manager, karigar_profile):
    resp = api(manager).delete(f"{KARIGARS}{karigar_profile.id}/")
    assert resp.status_code == 204
    karigar_profile.refresh_from_db()
    assert karigar_profile.is_active is False
    assert karigar_profile.user.is_active is False
