"""Pydantic (Ninja) schemas for the bandaki gold-loan API.

Interest / total / days-elapsed on ``BandakiLoanOut`` are **computed at
serialisation time** against today's date, so every response reflects the
current amount owed — the client never has to recompute it.
"""
from datetime import date, datetime
from decimal import Decimal

from ninja import Schema


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
# Loan
# ---------------------------------------------------------------------------
class BandakiLoanIn(Schema):
    customer: int
    loan_date: date
    gross_amount: Decimal
    interest_rate: Decimal
    interest_period: str = "monthly"
    remarks: str = ""


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
    gross_amount: Decimal            # principal
    interest_rate: Decimal
    interest_period: str
    interest_period_display: str
    interest_amount: str             # dynamic — accrued to today
    total_amount: str                # dynamic — principal + interest
    days_elapsed: int                # dynamic — days since loan_date
    is_active: bool
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
        return str(obj.interest_amount())

    @staticmethod
    def resolve_total_amount(obj):
        return str(obj.total_amount())

    @staticmethod
    def resolve_days_elapsed(obj):
        return obj.days_elapsed()


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
