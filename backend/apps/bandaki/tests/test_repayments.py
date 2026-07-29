"""Repayment arithmetic: byaj first, then sahu, then accrue on what is left.

The worked example throughout is a 100,000 loan at 2% monthly (30-day basis),
which grows exactly 2,000 a month — round numbers, so a wrong answer is
obvious rather than plausible.
"""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.bandaki.models import (
    BandakiCustomer,
    BandakiLoan,
    BandakiPayment,
    accrue,
    settle,
)

D = Decimal


def _days_ago(n):
    return timezone.localdate() - datetime.timedelta(days=n)


@pytest.fixture
def customer(shop, owner):
    return BandakiCustomer.objects.create(shop=shop, name="Hari", created_by=owner)


@pytest.fixture
def loan(shop, customer, owner):
    """100,000 at 2% monthly, taken 60 days ago."""
    return BandakiLoan.objects.create(
        shop=shop, customer=customer, loan_date=_days_ago(60),
        gross_amount=D("100000.00"), interest_rate=D("2"),
        interest_period="monthly", created_by=owner,
    )


def _pay(loan, days_ago, amount, owner=None):
    return BandakiPayment.objects.create(
        shop=loan.shop, loan=loan, payment_date=_days_ago(days_ago),
        amount=D(amount), created_by=owner,
    )


# ---------------------------------------------------------------------------
# The accrual primitive
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "principal,rate,period,days,expected",
    [
        ("100000", "2", "monthly", 30, "2000.00"),   # one whole month
        ("100000", "2", "monthly", 15, "1000.00"),   # pro-rated by the day
        ("100000", "12", "yearly", 365, "12000.00"),
        ("100000", "2", "monthly", 0, "0.00"),
        ("100000", "2", "monthly", -5, "0.00"),      # never negative
        ("0", "2", "monthly", 30, "0.00"),           # nothing owed, nothing charged
    ],
)
def test_accrue(principal, rate, period, days, expected):
    assert accrue(D(principal), D(rate), period, days) == D(expected)


# ---------------------------------------------------------------------------
# Settlement without repayments — must match the old plain accrual exactly
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_no_payments_matches_plain_accrual(loan):
    s = loan.settlement()
    assert s.principal_outstanding == D("100000.00")
    assert s.interest_outstanding == D("4000.00")   # 60 days = 2 months
    assert s.outstanding == D("104000.00")
    assert s.total_paid == D("0.00")
    assert not s.is_settled


# ---------------------------------------------------------------------------
# The headline behaviour: interest first, then principal, then accrue on less
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_partial_payment_clears_interest_then_cuts_principal(loan, owner):
    # Day 30 of 60: 2,000 of interest has accrued. Pay 30,000.
    _pay(loan, days_ago=30, amount="30000", owner=owner)
    s = loan.settlement()

    # 2,000 -> byaj, the remaining 28,000 -> sahu.
    assert s.interest_paid == D("2000.00")
    assert s.principal_paid == D("28000.00")
    assert s.principal_outstanding == D("72000.00")

    # The last 30 days accrue on 72,000, not on the original 100,000.
    assert s.interest_outstanding == D("1440.00")
    assert s.outstanding == D("73440.00")
    assert s.interest_accrued == D("3440.00")       # 2,000 + 1,440
    assert not s.is_settled


@pytest.mark.django_db
def test_interest_is_not_charged_on_money_already_returned(loan, owner):
    """The whole point of the segmented walk: paying down principal must cost
    the customer less than not paying it down."""
    without = loan.settlement().outstanding
    _pay(loan, days_ago=30, amount="30000", owner=owner)
    with_payment = loan.settlement()

    naive = without - D("30000")                    # if interest ignored the payment
    assert with_payment.outstanding < naive
    assert naive - with_payment.outstanding == D("560.00")   # 30 days on 28,000


@pytest.mark.django_db
def test_payment_smaller_than_accrued_interest_carries(loan, owner):
    # Day 30: 2,000 accrued. Pay only 500 — none of it touches the sahu.
    _pay(loan, days_ago=30, amount="500", owner=owner)
    s = loan.settlement()
    assert s.interest_paid == D("500.00")
    assert s.principal_paid == D("0.00")
    assert s.principal_outstanding == D("100000.00")
    # 1,500 carried + 2,000 for the next 30 days on the full principal.
    assert s.interest_outstanding == D("3500.00")


@pytest.mark.django_db
def test_several_payments_walk_in_date_order(loan, owner):
    _pay(loan, days_ago=40, amount="10000", owner=owner)   # day 20
    _pay(loan, days_ago=20, amount="20000", owner=owner)   # day 40
    s = loan.settlement()

    # Day 20: interest = 100,000 * 2% * 20/30 = 1,333.33; 8,666.67 cuts sahu.
    # Day 40: interest = 91,333.33 * 2% * 20/30 = 1,217.78; 18,782.22 cuts sahu.
    # Day 60: interest =  72,551.11 * 2% * 20/30 = 967.35, unpaid.
    assert s.principal_outstanding == D("72551.11")
    assert s.interest_outstanding == D("967.35")
    assert s.total_paid == D("30000.00")
    assert s.interest_paid + s.principal_paid == s.total_paid


@pytest.mark.django_db
def test_back_dated_payment_re_derives_everything_after_it(loan, owner):
    _pay(loan, days_ago=20, amount="20000", owner=owner)
    before = loan.settlement().outstanding

    # Slot an earlier payment in behind it. The later payment's split changes
    # too, because it now lands on a smaller principal.
    _pay(loan, days_ago=40, amount="10000", owner=owner)
    loan.refresh_from_db()
    after = loan.settlement()

    assert after.outstanding < before - D("10000")
    assert after.principal_outstanding == D("72551.11")


# ---------------------------------------------------------------------------
# Full settlement closes the loan and stops the clock
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_paying_everything_settles_the_loan(loan, owner):
    _pay(loan, days_ago=0, amount="104000", owner=owner)
    s = loan.settlement()
    assert s.principal_outstanding == D("0.00")
    assert s.interest_outstanding == D("0.00")
    assert s.is_settled
    assert s.settled_on == timezone.localdate()


@pytest.mark.django_db
def test_closure_freezes_the_figures(loan, owner):
    _pay(loan, days_ago=0, amount="104000", owner=owner)
    loan.sync_closure(owner)
    loan.refresh_from_db()
    assert loan.is_active is False
    assert loan.closed_on == timezone.localdate()

    # A closed loan reckons to its closing date, so tomorrow it still reads
    # zero rather than sprouting fresh interest.
    tomorrow = timezone.localdate() + datetime.timedelta(days=1)
    assert loan.reckoning_date() == loan.closed_on
    assert loan.settlement().outstanding == D("0.00")
    # Explicitly asking about tomorrow does accrue — but only on zero principal.
    assert loan.settlement(as_of=tomorrow).outstanding == D("0.00")


@pytest.mark.django_db
def test_removing_a_payment_reopens_the_loan(loan, owner):
    p = _pay(loan, days_ago=0, amount="104000", owner=owner)
    loan.sync_closure(owner)
    assert loan.is_active is False

    p.delete()
    loan = BandakiLoan.objects.get(pk=loan.pk)
    loan.sync_closure(owner)
    loan.refresh_from_db()
    assert loan.is_active is True
    assert loan.closed_on is None


# ---------------------------------------------------------------------------
# as_of: the same walk answers "where did this stand back then?"
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_as_of_ignores_later_payments(loan, owner):
    _pay(loan, days_ago=10, amount="50000", owner=owner)
    # Ask about day 30, before that payment existed.
    s = loan.settlement(as_of=_days_ago(30))
    assert s.total_paid == D("0.00")
    assert s.principal_outstanding == D("100000.00")
    assert s.interest_outstanding == D("2000.00")


# ---------------------------------------------------------------------------
# Overpayment is surfaced, not swallowed
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_overpayment_is_reported(loan):
    payments = [
        type("P", (), {"payment_date": timezone.localdate(), "amount": D("200000")})()
    ]
    s = settle(loan.gross_amount, loan.interest_rate, loan.interest_period,
               loan.loan_date, payments, timezone.localdate())
    assert s.overpaid == D("96000.00")   # 200,000 paid against 104,000 owed
    assert s.principal_outstanding == D("0.00")


# ===========================================================================
# API
# ===========================================================================
@pytest.mark.django_db
def test_receive_payment_endpoint_returns_the_resettled_loan(api, owner, loan):
    c = api(owner)
    r = c.post(f"/api/v1/bandaki/loans/{loan.id}/payments/",
               {"payment_date": str(_days_ago(30)), "amount": "30000", "remarks": "part"})
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["principal_outstanding"] == "72000.00"
    assert body["interest_amount"] == "1440.00"
    assert body["total_amount"] == "73440.00"
    assert body["total_paid"] == "30000.00"
    assert body["payment_count"] == 1
    assert body["is_active"] is True


@pytest.mark.django_db
def test_payment_history_shows_the_split(api, owner, loan):
    c = api(owner)
    c.post(f"/api/v1/bandaki/loans/{loan.id}/payments/",
           {"payment_date": str(_days_ago(30)), "amount": "30000"})
    r = c.get(f"/api/v1/bandaki/loans/{loan.id}/payments/")
    assert r.status_code == 200
    (row,) = r.json()
    assert row["interest_part"] == "2000.00"
    assert row["principal_part"] == "28000.00"
    assert row["principal_after"] == "72000.00"


@pytest.mark.django_db
def test_full_payment_closes_the_loan_via_the_api(api, owner, loan):
    c = api(owner)
    r = c.post(f"/api/v1/bandaki/loans/{loan.id}/payments/",
               {"payment_date": str(timezone.localdate()), "amount": "104000"})
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["is_active"] is False
    assert body["closed_on"] == str(timezone.localdate())
    assert body["total_amount"] == "0.00"


@pytest.mark.django_db
def test_overpayment_is_refused(api, owner, loan):
    c = api(owner)
    r = c.post(f"/api/v1/bandaki/loans/{loan.id}/payments/",
               {"payment_date": str(timezone.localdate()), "amount": "200000"})
    assert r.status_code == 400
    assert "more than this loan owes" in r.json()["error"]["message"]


@pytest.mark.django_db
def test_payment_cannot_predate_the_loan(api, owner, loan):
    c = api(owner)
    r = c.post(f"/api/v1/bandaki/loans/{loan.id}/payments/",
               {"payment_date": str(_days_ago(90)), "amount": "1000"})
    assert r.status_code == 400
    assert "predate" in r.json()["error"]["message"]


@pytest.mark.django_db
def test_deleting_a_payment_reopens_via_the_api(api, owner, loan):
    c = api(owner)
    c.post(f"/api/v1/bandaki/loans/{loan.id}/payments/",
           {"payment_date": str(timezone.localdate()), "amount": "104000"})
    pid = c.get(f"/api/v1/bandaki/loans/{loan.id}/payments/").json()[0]["id"]

    r = c.delete(f"/api/v1/bandaki/payments/{pid}/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["is_active"] is True
    assert body["closed_on"] is None
    assert body["total_amount"] == "104000.00"


@pytest.mark.django_db
def test_editing_a_payment_re_settles(api, owner, loan):
    c = api(owner)
    c.post(f"/api/v1/bandaki/loans/{loan.id}/payments/",
           {"payment_date": str(_days_ago(30)), "amount": "30000"})
    pid = c.get(f"/api/v1/bandaki/loans/{loan.id}/payments/").json()[0]["id"]

    r = c.patch(f"/api/v1/bandaki/payments/{pid}/", {"amount": "10000"})
    assert r.status_code == 200, r.content
    # 2,000 byaj + 8,000 sahu -> 92,000 principal, then 30 days at 2%.
    assert r.json()["principal_outstanding"] == "92000.00"
    assert r.json()["interest_amount"] == "1840.00"


@pytest.mark.django_db
def test_payments_are_shop_scoped(api, owner, other_shop, loan):
    """A second shop's owner cannot see or touch this loan's payments."""
    from apps.accounts.models import Role, User

    intruder = User(username="other-owner", role=Role.OWNER, shop=other_shop,
                    full_name="Other")
    intruder.set_password("Karigar@123")
    intruder.save()

    r = api(intruder).post(f"/api/v1/bandaki/loans/{loan.id}/payments/",
                           {"payment_date": str(timezone.localdate()), "amount": "100"})
    assert r.status_code == 404


@pytest.mark.django_db
def test_non_owner_cannot_receive_payments(api, manager, loan):
    r = api(manager).post(f"/api/v1/bandaki/loans/{loan.id}/payments/",
                          {"payment_date": str(timezone.localdate()), "amount": "100"})
    assert r.status_code == 403
