"""Pledged gold: what the shop is holding, and letting it go piece by piece.

The gold here is the *customer's* property held as security. It must never mix
with the karigar gold ledger, and the record has to survive a piece going back —
so a return is a date on the item, never a deletion.
"""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.bandaki.models import BandakiCustomer, BandakiItem, BandakiLoan
from apps.ledger.models import GoldEntry, Ornament

D = Decimal


@pytest.fixture
def customer(shop, owner):
    return BandakiCustomer.objects.create(shop=shop, name="Hari", created_by=owner)


@pytest.fixture
def loan(shop, customer, owner):
    return BandakiLoan.objects.create(
        shop=shop, customer=customer,
        loan_date=timezone.localdate() - datetime.timedelta(days=60),
        gross_amount=D("100000.00"), interest_rate=D("2"),
        interest_period="monthly", created_by=owner,
    )


@pytest.fixture
def chain(shop):
    return Ornament.objects.get_or_create(shop=shop, name="Chain")[0]


@pytest.fixture
def ring(shop):
    return Ornament.objects.get_or_create(shop=shop, name="Ring")[0]


def _pledge(loan, ornament, gross, carat=22, qty=1):
    return BandakiItem.objects.create(
        shop=loan.shop, loan=loan, ornament=ornament,
        gross_weight_g=D(gross), carat=carat, quantity=qty,
    )


# ---------------------------------------------------------------------------
# Net weight follows the same rule as the gold ledger
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@pytest.mark.parametrize(
    "gross,carat,expected",
    [
        ("24.000", 24, "24.000"),   # pure — net == gross
        ("24.000", 22, "22.000"),
        ("10.000", 22, "9.167"),    # 10 * 22/24 rounded to 3dp
    ],
)
def test_net_weight_matches_the_ledger_rule(loan, chain, gross, carat, expected):
    item = _pledge(loan, chain, gross, carat)
    assert item.net_weight_g == D(expected)


@pytest.mark.django_db
def test_net_weight_recomputed_when_carat_is_corrected(loan, chain):
    item = _pledge(loan, chain, "24.000", 22)
    assert item.net_weight_g == D("22.000")
    item.carat = 24
    item.save()
    assert item.net_weight_g == D("24.000")


@pytest.mark.django_db
def test_pledged_gold_stays_out_of_the_karigar_ledger(loan, chain, shop):
    """Customer collateral is not shop stock — it must not appear as a
    GoldEntry, or karigar balances would silently absorb it."""
    _pledge(loan, chain, "50.000")
    assert GoldEntry.objects.filter(shop=shop).count() == 0


# ---------------------------------------------------------------------------
# What the shop is still holding
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_held_weight_sums_quantity(loan, chain, ring):
    _pledge(loan, chain, "22.500", 22)          # net 20.625
    _pledge(loan, ring, "8.200", 22, qty=2)     # net 7.517 each
    loan.refresh_from_db()
    # 20.625 + (7.517 * 2)
    assert loan.net_weight_held_g() == D("35.659")
    assert len(loan.items_held()) == 2


@pytest.mark.django_db
def test_returning_a_piece_removes_it_from_the_held_total(loan, chain, ring):
    _pledge(loan, chain, "22.500")
    r = _pledge(loan, ring, "8.200")
    r.returned_on = timezone.localdate()
    r.save()

    loan = BandakiLoan.objects.get(pk=loan.pk)
    assert loan.net_weight_held_g() == D("20.625")
    assert [i.ornament.name for i in loan.items_held()] == ["Chain"]
    # The returned piece is still on record — history, not deletion.
    assert loan.items.count() == 2
    assert r.is_held is False


# ===========================================================================
# API
# ===========================================================================
@pytest.mark.django_db
def test_loan_created_with_its_pledged_pieces(api, owner, customer, chain, ring):
    r = api(owner).post("/api/v1/bandaki/loans/", {
        "customer": customer.id,
        "loan_date": str(timezone.localdate()),
        "gross_amount": "100000",
        "interest_rate": "2",
        "interest_period": "monthly",
        "items": [
            {"ornament": chain.id, "quantity": 1, "gross_weight_g": "22.500", "carat": 22},
            {"ornament": ring.id, "quantity": 2, "gross_weight_g": "8.200", "carat": 22,
             "description": "matching pair"},
        ],
    })
    assert r.status_code == 201, r.content
    body = r.json()
    assert len(body["items"]) == 2
    assert body["items_held_count"] == 3           # 1 chain + 2 rings
    assert body["net_weight_held_g"] == "35.659"
    assert body["items"][0]["ornament_name"] == "Chain"
    assert body["items"][1]["description"] == "matching pair"
    assert body["items"][0]["is_held"] is True


@pytest.mark.django_db
def test_a_bad_item_rolls_back_the_whole_loan(api, owner, customer, chain):
    """The loan and its gold are one act of recording — a rejected piece must
    not leave a half-recorded loan behind."""
    before = BandakiLoan.objects.count()
    r = api(owner).post("/api/v1/bandaki/loans/", {
        "customer": customer.id,
        "loan_date": str(timezone.localdate()),
        "gross_amount": "100000",
        "interest_rate": "2",
        "items": [
            {"ornament": chain.id, "gross_weight_g": "22.500", "carat": 22},
            {"ornament": 999999, "gross_weight_g": "1.000", "carat": 22},
        ],
    })
    assert r.status_code == 400
    assert BandakiLoan.objects.count() == before
    assert BandakiItem.objects.count() == 0


@pytest.mark.django_db
def test_add_a_piece_to_a_running_loan(api, owner, loan, chain):
    r = api(owner).post(f"/api/v1/bandaki/loans/{loan.id}/items/", {
        "ornament": chain.id, "quantity": 1, "gross_weight_g": "10.000", "carat": 24,
    })
    assert r.status_code == 201, r.content
    assert r.json()["net_weight_held_g"] == "10.000"


@pytest.mark.django_db
def test_return_a_piece_via_the_api(api, owner, loan, chain, ring):
    c = api(owner)
    c.post(f"/api/v1/bandaki/loans/{loan.id}/items/",
           {"ornament": chain.id, "gross_weight_g": "22.500", "carat": 22})
    r = c.post(f"/api/v1/bandaki/loans/{loan.id}/items/",
               {"ornament": ring.id, "gross_weight_g": "8.200", "carat": 22})
    ring_id = r.json()["items"][1]["id"]

    today = str(timezone.localdate())
    r = c.patch(f"/api/v1/bandaki/items/{ring_id}/", {"returned_on": today})
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["net_weight_held_g"] == "20.625"
    assert body["items_held_count"] == 1
    returned = next(i for i in body["items"] if i["id"] == ring_id)
    assert returned["returned_on"] == today
    assert returned["is_held"] is False


@pytest.mark.django_db
def test_a_return_can_be_undone(api, owner, loan, chain):
    c = api(owner)
    r = c.post(f"/api/v1/bandaki/loans/{loan.id}/items/",
               {"ornament": chain.id, "gross_weight_g": "22.500", "carat": 22})
    iid = r.json()["items"][0]["id"]
    c.patch(f"/api/v1/bandaki/items/{iid}/", {"returned_on": str(timezone.localdate())})

    r = c.patch(f"/api/v1/bandaki/items/{iid}/", {"returned_on": None})
    assert r.status_code == 200, r.content
    assert r.json()["items_held_count"] == 1


@pytest.mark.django_db
def test_piece_cannot_be_returned_before_the_loan(api, owner, loan, chain):
    c = api(owner)
    r = c.post(f"/api/v1/bandaki/loans/{loan.id}/items/",
               {"ornament": chain.id, "gross_weight_g": "22.500", "carat": 22})
    iid = r.json()["items"][0]["id"]
    too_early = str(loan.loan_date - datetime.timedelta(days=1))
    r = c.patch(f"/api/v1/bandaki/items/{iid}/", {"returned_on": too_early})
    assert r.status_code == 400
    assert "before the loan" in r.json()["error"]["message"]


@pytest.mark.django_db
def test_bad_carat_is_refused(api, owner, loan, chain):
    r = api(owner).post(f"/api/v1/bandaki/loans/{loan.id}/items/",
                        {"ornament": chain.id, "gross_weight_g": "10.000", "carat": 18})
    assert r.status_code == 400
    assert "22 or 24" in r.json()["error"]["message"]


@pytest.mark.django_db
def test_ornament_from_another_shop_is_refused(api, owner, loan, other_shop):
    theirs = Ornament.objects.create(shop=other_shop, name="Anklet")
    r = api(owner).post(f"/api/v1/bandaki/loans/{loan.id}/items/",
                        {"ornament": theirs.id, "gross_weight_g": "10.000", "carat": 22})
    assert r.status_code == 400
    assert "Unknown ornament" in r.json()["error"]["message"]


@pytest.mark.django_db
def test_non_owner_cannot_touch_pledged_gold(api, manager, loan, chain):
    r = api(manager).get(f"/api/v1/bandaki/loans/{loan.id}/items/")
    assert r.status_code == 403
