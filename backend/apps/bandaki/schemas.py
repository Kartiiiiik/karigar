"""Pydantic (Ninja) schemas for the bandaki gold-loan API.

Interest / totals / days-elapsed on ``BandakiLoanOut`` are **computed at
serialisation time** by walking the loan's repayments up to today, so every
response reflects the current amount owed — the client never has to recompute
it.
"""
from datetime import date, datetime
from decimal import Decimal

from ninja import Schema


def _settlement(obj):
    """The loan's settlement, computed once per serialised row.

    Each field below needs a piece of the same walk; without this the walk
    would run a dozen times per loan.
    """
    s = getattr(obj, "_settlement_cache", None)
    if s is None:
        s = obj.settlement()
        obj._settlement_cache = s
    return s


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
class BandakiCustomerIn(Schema):
    name: str
    phone: str = ""
    location: str = ""
    remarks: str = ""


class BandakiCustomerPatch(Schema):
    name: str | None = None
    phone: str | None = None
    location: str | None = None
    remarks: str | None = None
    is_active: bool | None = None


class BandakiCustomerOut(Schema):
    id: int
    name: str
    phone: str = ""
    location: str = ""
    remarks: str = ""
    is_active: bool
    loan_count: int = 0
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def resolve_loan_count(obj):
        # Annotated by the list queryset; falls back to a count for detail reads.
        n = getattr(obj, "_loan_count", None)
        return n if n is not None else obj.loans.count()


# ---------------------------------------------------------------------------
# Pledged gold
# ---------------------------------------------------------------------------
class BandakiItemIn(Schema):
    ornament: int
    quantity: int = 1
    gross_weight_g: Decimal
    carat: int = 22
    description: str = ""


class BandakiItemPatch(Schema):
    ornament: int | None = None
    quantity: int | None = None
    gross_weight_g: Decimal | None = None
    carat: int | None = None
    description: str | None = None
    # Set to hand a piece back; null to undo a return recorded by mistake.
    returned_on: date | None = None


class BandakiItemOut(Schema):
    id: int
    loan: int
    ornament: int
    ornament_name: str
    description: str = ""
    quantity: int
    gross_weight_g: Decimal
    carat: int
    net_weight_g: Decimal        # gross x carat/24, stored at save time
    returned_on: date | None = None
    is_held: bool

    @staticmethod
    def resolve_loan(obj):
        return obj.loan_id

    @staticmethod
    def resolve_ornament(obj):
        return obj.ornament_id

    @staticmethod
    def resolve_ornament_name(obj):
        return obj.ornament.name


# ---------------------------------------------------------------------------
# Loan
# ---------------------------------------------------------------------------
class BandakiLoanIn(Schema):
    customer: int
    loan_date: date
    gross_amount: Decimal
    interest_rate: Decimal
    interest_period: str = "monthly"
    remarks: str = ""
    # Pledged pieces are captured with the loan — the gold and the money change
    # hands in the same conversation.
    items: list[BandakiItemIn] = []


class BandakiLoanPatch(Schema):
    customer: int | None = None
    loan_date: date | None = None
    gross_amount: Decimal | None = None
    interest_rate: Decimal | None = None
    interest_period: str | None = None
    remarks: str | None = None
    is_active: bool | None = None


class BandakiLoanOut(Schema):
    id: int
    customer: int
    customer_name: str
    loan_date: date
    gross_amount: Decimal            # principal originally lent — never moves
    interest_rate: Decimal
    interest_period: str
    interest_period_display: str
    # Everything below is derived on read by walking the repayments.
    interest_amount: str             # interest owed now (accrued, unpaid)
    total_amount: str                # everything still owed
    principal_outstanding: str       # sahu still owed
    interest_accrued: str            # interest charged over the loan's whole life
    interest_paid: str
    principal_paid: str
    total_paid: str
    payment_count: int
    days_elapsed: int                # days the loan has been running
    as_of: date                      # the day these figures are measured to
    # Pledged gold, and how much of it the shop is still holding.
    items: list[BandakiItemOut] = []
    items_held_count: int = 0
    net_weight_held_g: str = "0.000"
    is_active: bool
    closed_on: date | None = None
    remarks: str = ""
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def resolve_customer(obj):
        return obj.customer_id

    @staticmethod
    def resolve_customer_name(obj):
        return obj.customer.name

    @staticmethod
    def resolve_interest_period_display(obj):
        return obj.get_interest_period_display()

    @staticmethod
    def resolve_interest_amount(obj):
        return str(_settlement(obj).interest_outstanding)

    @staticmethod
    def resolve_total_amount(obj):
        return str(_settlement(obj).outstanding)

    @staticmethod
    def resolve_principal_outstanding(obj):
        return str(_settlement(obj).principal_outstanding)

    @staticmethod
    def resolve_interest_accrued(obj):
        return str(_settlement(obj).interest_accrued)

    @staticmethod
    def resolve_interest_paid(obj):
        return str(_settlement(obj).interest_paid)

    @staticmethod
    def resolve_principal_paid(obj):
        return str(_settlement(obj).principal_paid)

    @staticmethod
    def resolve_total_paid(obj):
        return str(_settlement(obj).total_paid)

    @staticmethod
    def resolve_payment_count(obj):
        return len(obj.payments.all())

    @staticmethod
    def resolve_items_held_count(obj):
        return sum(i.quantity for i in obj.items_held())

    @staticmethod
    def resolve_net_weight_held_g(obj):
        return str(obj.net_weight_held_g())

    @staticmethod
    def resolve_as_of(obj):
        return _settlement(obj).as_of

    @staticmethod
    def resolve_days_elapsed(obj):
        return obj.days_elapsed()


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
class BandakiPaymentIn(Schema):
    payment_date: date
    amount: Decimal
    remarks: str = ""


class BandakiPaymentPatch(Schema):
    payment_date: date | None = None
    amount: Decimal | None = None
    remarks: str | None = None


class BandakiPaymentOut(Schema):
    """One repayment, plus how it landed against byaj and sahu.

    The split is not stored on the row — it depends on everything that came
    before it — so it is filled in by the endpoint that replays the timeline.
    """

    id: int
    loan: int
    payment_date: date
    amount: Decimal
    remarks: str = ""
    # Filled in by the payments endpoint; zero when read out of context.
    interest_part: str = "0.00"
    principal_part: str = "0.00"
    principal_after: str = "0.00"
    outstanding_after: str = "0.00"
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def resolve_loan(obj):
        return obj.loan_id


# ---------------------------------------------------------------------------
# History (reused shape from the ledger app)
# ---------------------------------------------------------------------------
class HistoryChange(Schema):
    field: str
    old: str
    new: str


class HistoryOut(Schema):
    history_id: int
    type: str
    date: datetime
    user: str | None = None
    changes: list[HistoryChange] = []
