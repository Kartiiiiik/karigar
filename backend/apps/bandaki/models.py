"""Bandaki domain: gold-loan customers and their loans.

*Bandaki* (बन्धकी) is a pawn / gold loan: a customer hands over gold and the
shop lends them money against it at some interest. Interest **accrues with
time** — it is never stored as a fixed figure. Instead it is recomputed from
the loan date up to *today* on every read (see :func:`compute_interest`), so
the amount owed is always current the moment the page is opened.

Money is NPR (Decimal, 2dp). Dates are stored in AD; BS is a display concern
only, exactly as in the ledger app.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.common.models import AuthoredModel

MONEY_QUANT = Decimal("0.01")

# Day-count basis for simple interest. Monthly loans charge `rate`% per 30
# days; yearly loans charge `rate`% per 365 days. Interest is pro-rated by the
# actual number of days elapsed so it grows continuously, day by day.
DAYS_PER_MONTH = Decimal("30")
DAYS_PER_YEAR = Decimal("365")


class InterestPeriod(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"


def compute_interest(principal, rate, period, loan_date, as_of=None):
    """Simple interest accrued from ``loan_date`` up to ``as_of`` (today).

    interest = principal × (rate/100) × (days_elapsed / days_in_period)

    Dynamic by design: pass no ``as_of`` and it uses today's date in the shop
    timezone, so the figure is always fresh on read. Never negative (a future
    loan date yields zero until it arrives).
    """
    if as_of is None:
        as_of = timezone.localdate()
    principal = Decimal(str(principal))
    rate = Decimal(str(rate))
    days = Decimal((as_of - loan_date).days)
    if days < 0:
        days = Decimal("0")
    basis = DAYS_PER_MONTH if period == InterestPeriod.MONTHLY else DAYS_PER_YEAR
    interest = principal * (rate / Decimal("100")) * (days / basis)
    return interest.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


class BandakiCustomer(AuthoredModel):
    """A person who takes gold loans from the shop."""

    shop = models.ForeignKey(
        "accounts.Shop", on_delete=models.CASCADE, related_name="bandaki_customers"
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=300, blank=True)
    remarks = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class BandakiLoan(AuthoredModel):
    """A single gold loan: principal lent to a customer at some interest.

    ``gross_amount`` is the principal handed over. ``interest_rate`` is a
    percentage applied per ``interest_period`` (monthly/yearly). The interest
    and total owed are **not stored** — they are computed on read from the
    elapsed time (see :func:`compute_interest`).
    """

    shop = models.ForeignKey(
        "accounts.Shop", on_delete=models.CASCADE, related_name="bandaki_loans"
    )
    customer = models.ForeignKey(
        BandakiCustomer, on_delete=models.PROTECT, related_name="loans"
    )
    loan_date = models.DateField(db_index=True)
    gross_amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    interest_rate = models.DecimalField(
        max_digits=6, decimal_places=3, validators=[MinValueValidator(Decimal("0"))]
    )
    interest_period = models.CharField(
        max_length=10, choices=InterestPeriod.choices, default=InterestPeriod.MONTHLY
    )
    remarks = models.TextField(blank=True)
    # A loan stays active until it is repaid/closed. Closed loans stop accruing
    # in the UI but are kept for history.
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-loan_date", "-created_at"]
        indexes = [
            models.Index(fields=["shop", "loan_date"]),
            models.Index(fields=["customer", "is_active"]),
        ]

    def __str__(self):
        return f"{self.customer.name} — NPR {self.gross_amount}"

    # -- Dynamic interest ---------------------------------------------------
    def interest_amount(self, as_of: date | None = None) -> Decimal:
        """Interest accrued to ``as_of`` (default today). Recomputed on read."""
        return compute_interest(
            self.gross_amount, self.interest_rate, self.interest_period,
            self.loan_date, as_of,
        )

    def total_amount(self, as_of: date | None = None) -> Decimal:
        """Principal + accrued interest to ``as_of`` (default today)."""
        return (self.gross_amount + self.interest_amount(as_of)).quantize(MONEY_QUANT)

    def days_elapsed(self, as_of: date | None = None) -> int:
        if as_of is None:
            as_of = timezone.localdate()
        return max(0, (as_of - self.loan_date).days)
