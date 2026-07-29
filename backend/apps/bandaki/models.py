"""Bandaki domain: gold-loan customers, their loans, and repayments.

*Bandaki* (बन्धकी) is a pawn / gold loan: a customer hands over gold and the
shop lends them money against it at some interest. Interest **accrues with
time** — it is never stored as a fixed figure. Instead it is recomputed from
the loan date up to *today* on every read (see :func:`compute_interest`), so
the amount owed is always current the moment the page is opened.

Repayments follow the shop's practice: a payment clears the accrued *byaj*
(interest) first, and only the surplus cuts the *sahu* (principal). Interest
from that day on accrues on the reduced principal — so the timeline is walked
segment by segment rather than in one shot (see :func:`settle`).

Money is NPR (Decimal, 2dp). Dates are stored in AD; BS is a display concern
only, exactly as in the ledger app.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.common.models import AuthoredModel

# Pledged gold is weighed exactly like the shop's own metal, so the carat
# options and the gross->net conversion are shared rather than reinvented.
from apps.ledger.models import CARAT_22, CARAT_CHOICES, compute_net_weight

MONEY_QUANT = Decimal("0.01")

# Day-count basis for simple interest. Monthly loans charge `rate`% per 30
# days; yearly loans charge `rate`% per 365 days. Interest is pro-rated by the
# actual number of days elapsed so it grows continuously, day by day.
DAYS_PER_MONTH = Decimal("30")
DAYS_PER_YEAR = Decimal("365")


class InterestPeriod(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"


def accrue(principal, rate, period, days):
    """Simple interest on ``principal`` over ``days``.

    interest = principal × (rate/100) × (days / days_in_period)

    Never negative — a negative span accrues nothing.
    """
    principal = Decimal(str(principal))
    rate = Decimal(str(rate))
    days = Decimal(days)
    if days < 0 or principal <= 0:
        return Decimal("0.00").quantize(MONEY_QUANT)
    basis = DAYS_PER_MONTH if period == InterestPeriod.MONTHLY else DAYS_PER_YEAR
    interest = principal * (rate / Decimal("100")) * (days / basis)
    return interest.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def compute_interest(principal, rate, period, loan_date, as_of=None):
    """Simple interest accrued from ``loan_date`` up to ``as_of`` (today).

    Dynamic by design: pass no ``as_of`` and it uses today's date in the shop
    timezone, so the figure is always fresh on read. Never negative (a future
    loan date yields zero until it arrives).

    This is the *no repayments* case. Once a loan has payments the timeline has
    to be walked segment by segment — see :func:`settle`.
    """
    if as_of is None:
        as_of = timezone.localdate()
    return accrue(principal, rate, period, (as_of - loan_date).days)


@dataclass
class PaymentLine:
    """How one repayment landed, and the balance it left behind."""

    payment: object
    interest_part: Decimal
    principal_part: Decimal
    principal_after: Decimal
    outstanding_after: Decimal


@dataclass
class Settlement:
    """Where a loan stands on a given day, after applying its repayments.

    ``principal_outstanding`` + ``interest_outstanding`` == ``outstanding``,
    the figure the customer would hand over to walk away with their gold.
    """

    as_of: date
    principal_outstanding: Decimal = field(default_factory=lambda: Decimal("0.00"))
    interest_outstanding: Decimal = field(default_factory=lambda: Decimal("0.00"))
    interest_accrued: Decimal = field(default_factory=lambda: Decimal("0.00"))
    interest_paid: Decimal = field(default_factory=lambda: Decimal("0.00"))
    principal_paid: Decimal = field(default_factory=lambda: Decimal("0.00"))
    total_paid: Decimal = field(default_factory=lambda: Decimal("0.00"))
    # Paid beyond everything owed. Should always be zero — the API refuses
    # payments that would push it positive — but it is surfaced rather than
    # silently swallowed so bad data is visible instead of invisible.
    overpaid: Decimal = field(default_factory=lambda: Decimal("0.00"))
    # The date the balance first reached zero, if it ever did.
    settled_on: date | None = None
    # One entry per repayment applied, in the order they were applied: how that
    # payment split between byaj and sahu, and where it left the loan. This is
    # what the payment-history panel shows — it cannot be read off the payment
    # rows themselves, since the split depends on everything before it.
    lines: list["PaymentLine"] = field(default_factory=list)

    @property
    def outstanding(self) -> Decimal:
        return (self.principal_outstanding + self.interest_outstanding).quantize(MONEY_QUANT)

    @property
    def is_settled(self) -> bool:
        return self.outstanding <= 0


def settle(principal, rate, period, loan_date, payments, as_of=None) -> Settlement:
    """Walk a loan's repayments in date order and report where it stands.

    Between one event and the next, interest accrues on whatever principal is
    outstanding *during that span*. Each payment then clears accrued interest
    first and puts the surplus against principal — so a customer who pays down
    the sahu stops paying byaj on the part they returned.

    ``payments`` is any iterable of objects with ``payment_date`` and
    ``amount``; it is sorted here, so callers need not pre-order it. Payments
    dated after ``as_of`` are ignored, which is what makes back-dated entry and
    "where did this stand last month?" both work off the same code path.
    """
    if as_of is None:
        as_of = timezone.localdate()

    s = Settlement(as_of=as_of)
    outstanding_principal = Decimal(str(principal))
    interest_due = Decimal("0.00")
    cursor = loan_date

    # Sorted by date alone: Python's sort is stable, and same-day payments give
    # the same result in any order (no interest accrues across a zero-day span,
    # and the interest-then-principal waterfall is linear in the amount).
    relevant = sorted(
        (p for p in payments if p.payment_date <= as_of),
        key=lambda p: p.payment_date,
    )

    for p in relevant:
        # Accrue over the span that just ended, on the principal that stood
        # during it. A payment back-dated before the loan simply accrues zero.
        grown = accrue(outstanding_principal, rate, period, (p.payment_date - cursor).days)
        interest_due += grown
        s.interest_accrued += grown
        cursor = max(cursor, p.payment_date)

        left = Decimal(str(p.amount))
        # Byaj first...
        to_interest = min(left, interest_due)
        interest_due -= to_interest
        left -= to_interest
        # ...then sahu.
        to_principal = min(left, outstanding_principal)
        outstanding_principal -= to_principal
        left -= to_principal

        s.interest_paid += to_interest
        s.principal_paid += to_principal
        s.total_paid += Decimal(str(p.amount))
        s.overpaid += left
        s.lines.append(
            PaymentLine(
                payment=p,
                interest_part=to_interest.quantize(MONEY_QUANT),
                principal_part=to_principal.quantize(MONEY_QUANT),
                principal_after=outstanding_principal.quantize(MONEY_QUANT),
                outstanding_after=(outstanding_principal + interest_due).quantize(MONEY_QUANT),
            )
        )

        if s.settled_on is None and outstanding_principal <= 0 and interest_due <= 0:
            s.settled_on = p.payment_date

    # Tail segment: from the last event up to the day we are asking about.
    tail = accrue(outstanding_principal, rate, period, (as_of - cursor).days)
    interest_due += tail
    s.interest_accrued += tail

    s.principal_outstanding = outstanding_principal.quantize(MONEY_QUANT)
    s.interest_outstanding = interest_due.quantize(MONEY_QUANT)
    return s


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

    ``gross_amount`` is the principal originally handed over — it never moves.
    What the customer still owes is derived from it plus the repayments (see
    :meth:`settlement`); nothing about the current balance is stored, so the
    figures are always current the moment they are read.
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
    # A loan stays active until it is repaid/closed. Closed loans are kept for
    # history but stop accruing — see `closed_on`.
    is_active = models.BooleanField(default=True)
    # The day the loan stopped running: the date of the payment that cleared it,
    # or the day the owner closed it by hand. Interest is measured up to this
    # date rather than to today, so a closed loan's figures stand still instead
    # of drifting upward forever.
    closed_on = models.DateField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-loan_date", "-created_at"]
        indexes = [
            models.Index(fields=["shop", "loan_date"]),
            models.Index(fields=["customer", "is_active"]),
        ]

    def __str__(self):
        return f"{self.customer.name} — NPR {self.gross_amount}"

    # -- Dynamic settlement --------------------------------------------------
    def reckoning_date(self, as_of: date | None = None) -> date:
        """The day the figures are measured to. Today for a running loan; the
        closing date for one that has stopped."""
        if as_of is not None:
            return as_of
        if not self.is_active and self.closed_on:
            return self.closed_on
        return timezone.localdate()

    def settlement(self, as_of: date | None = None) -> Settlement:
        """Where this loan stands, repayments applied. Recomputed on read.

        Uses ``self.payments`` — prefetch it on list views to avoid an extra
        query per row.
        """
        return settle(
            self.gross_amount, self.interest_rate, self.interest_period,
            self.loan_date, self.payments.all(), self.reckoning_date(as_of),
        )

    def interest_amount(self, as_of: date | None = None) -> Decimal:
        """Interest currently owed — accrued but not yet paid off. Matches the
        plain accrual exactly when the loan has no repayments."""
        return self.settlement(as_of).interest_outstanding

    def total_amount(self, as_of: date | None = None) -> Decimal:
        """Everything still owed: outstanding principal + outstanding interest."""
        return self.settlement(as_of).outstanding

    def days_elapsed(self, as_of: date | None = None) -> int:
        return max(0, (self.reckoning_date(as_of) - self.loan_date).days)

    # -- Pledged gold --------------------------------------------------------
    def items_held(self):
        """Pieces the shop is still holding (not yet handed back)."""
        return [i for i in self.items.all() if i.returned_on is None]

    def net_weight_held_g(self) -> Decimal:
        """Total net gold still in the shop's keeping for this loan."""
        total = sum((i.net_weight_g * i.quantity for i in self.items_held()), Decimal("0"))
        return Decimal(total).quantize(Decimal("0.001"))

    def sync_closure(self, user=None) -> bool:
        """Close the loan once it is fully repaid, reopen it if it is not.

        Called after any repayment is written or removed, so the status follows
        the money instead of having to be toggled by hand. Returns whether the
        loan was changed.
        """
        # Measure against today, not `closed_on` — otherwise a loan already
        # closed would keep reporting the frozen balance and never reopen.
        s = settle(
            self.gross_amount, self.interest_rate, self.interest_period,
            self.loan_date, self.payments.all(), timezone.localdate(),
        )
        was_active, was_closed_on = self.is_active, self.closed_on
        if s.is_settled:
            self.is_active = False
            self.closed_on = s.settled_on or timezone.localdate()
        elif self.closed_on is not None:
            # A repayment was removed or reduced: the loan is running again.
            self.is_active = True
            self.closed_on = None
        if self.is_active == was_active and self.closed_on == was_closed_on:
            return False
        if user is not None:
            self.updated_by = user
        self.save(update_fields=["is_active", "closed_on", "updated_by", "updated_at"])
        return True


class BandakiItem(AuthoredModel):
    """One piece of gold pledged against a loan.

    This is the customer's property held as security — deliberately *not* a
    ledger ``GoldEntry``, which tracks the shop's own metal moving to and from
    karigars. Pledged gold never enters shop stock; it sits here until it goes
    back.

    Pieces are released individually: a customer who pays down a good chunk may
    take one bangle back while the chain stays. So the return date lives on the
    item, not on the loan.
    """

    shop = models.ForeignKey(
        "accounts.Shop", on_delete=models.CASCADE, related_name="bandaki_items"
    )
    loan = models.ForeignKey(BandakiLoan, on_delete=models.CASCADE, related_name="items")
    # Reuses the shop's ornament list, the same one the gold receive-form uses.
    ornament = models.ForeignKey(
        "ledger.Ornament", on_delete=models.PROTECT, related_name="bandaki_items"
    )
    # Distinguishing detail for identical ornament types — "thick chain with
    # locket" vs "plain chain" — so the right piece goes back.
    description = models.CharField(max_length=200, blank=True)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    gross_weight_g = models.DecimalField(
        max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    carat = models.PositiveSmallIntegerField(choices=CARAT_CHOICES, default=CARAT_22)
    # Stored, not derived on read: recomputed on every save so a historical
    # figure survives even if the carat constants ever change.
    net_weight_g = models.DecimalField(max_digits=12, decimal_places=3, editable=False)
    # Null while the shop still holds it.
    returned_on = models.DateField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [models.Index(fields=["loan", "returned_on"])]

    def __str__(self):
        return f"{self.quantity}x {self.ornament} ({self.gross_weight_g}g)"

    @property
    def is_held(self) -> bool:
        return self.returned_on is None

    def save(self, *args, **kwargs):
        self.net_weight_g = compute_net_weight(self.gross_weight_g, self.carat)
        super().save(*args, **kwargs)


class BandakiPayment(AuthoredModel):
    """Cash received from a customer against one bandaki loan.

    Deliberately *not* a ledger ``CashEntry``: the cash ledger is scoped to
    karigars, and a bandaki customer is not one. The amount is recorded as
    handed over — how it splits between byaj and sahu is derived by
    :func:`settle`, never stored, so back-dating or correcting a payment
    re-derives every figure that follows it.
    """

    shop = models.ForeignKey(
        "accounts.Shop", on_delete=models.CASCADE, related_name="bandaki_payments"
    )
    loan = models.ForeignKey(
        BandakiLoan, on_delete=models.CASCADE, related_name="payments"
    )
    payment_date = models.DateField(db_index=True)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    remarks = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["payment_date", "created_at"]
        indexes = [models.Index(fields=["loan", "payment_date"])]

    def __str__(self):
        return f"{self.payment_date} — NPR {self.amount}"
