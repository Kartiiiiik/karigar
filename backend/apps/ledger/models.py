"""Ledger domain: karigars, ornaments, orders, and the gold & cash entries.

Accounting conventions (from the shop's books):
  * Dr = given to the karigar  (gold/cash goes OUT to them)
  * Cr = received from karigar  (gold/ornament/cash comes BACK)

Signed balances used throughout:
  * A POSITIVE net balance means net **Dr** — the karigar currently holds the
    shop's gold/cash.
  * A NEGATIVE net balance means net **Cr** — the shop owes the karigar.

Weights are grams (Decimal, 3dp). Money is NPR (Decimal, 2dp). Dates are stored
in AD; BS is a display concern only.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce, Lower
from simple_history.models import HistoricalRecords

from apps.common.models import AuthoredModel, TimeStampedModel

# Carat options. 24 is pure; net = gross for 24kt. 22kt uses 22/24 exactly.
CARAT_22 = 22
CARAT_24 = 24
CARAT_CHOICES = [(CARAT_22, "22kt"), (CARAT_24, "24kt")]

GRAM_QUANT = Decimal("0.001")


class Direction(models.TextChoices):
    DR = "dr", "Debit (given to karigar)"
    CR = "cr", "Credit (received from karigar)"


def compute_net_weight(gross_weight, carat):
    """net_weight = gross_weight * (carat / 24), quantised to 3dp.

    24kt -> net == gross. 22kt -> gross * 22/24.
    """
    gross = Decimal(str(gross_weight))
    net = gross * (Decimal(carat) / Decimal(settings.GOLD_PURE_CARAT))
    return net.quantize(GRAM_QUANT, rounding=ROUND_HALF_UP)


class Ornament(TimeStampedModel):
    """A type of ornament (ring, chain, …). Powers the receive-form dropdown."""

    shop = models.ForeignKey("accounts.Shop", on_delete=models.CASCADE, related_name="ornaments")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # Case-insensitive uniqueness per shop ("Ring" == "ring" == "RING").
            models.UniqueConstraint(
                Lower("name"), "shop", name="uniq_ornament_name_ci_per_shop"
            )
        ]

    def __str__(self):
        return self.name


class KarigarProfile(AuthoredModel):
    """Extends a karigar ``User`` with shop-facing details and opening balances.

    Opening balances are signed: positive = opening Dr (karigar already holds
    the shop's gold/cash), negative = opening Cr (shop owes the karigar). They
    seed the running ledgers.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="karigar_profile"
    )
    shop = models.ForeignKey("accounts.Shop", on_delete=models.CASCADE, related_name="karigars")
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=300, blank=True)
    photo = models.ImageField(upload_to="karigars/", blank=True, null=True)
    # Plaintext login password kept so owner/manager can re-share it with the
    # karigar on request. Deliberate product choice for this internal shop tool;
    # only ever exposed on the staff-only karigar endpoints.
    plain_password = models.CharField(max_length=128, blank=True)

    # Signed opening balances (see class docstring).
    opening_gold_g = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    opening_cash_npr = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    joined_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    # -- Balances -----------------------------------------------------------
    def gold_balance(self):
        """Signed net gold balance in grams (+Dr / -Cr)."""
        agg = self.gold_entries.aggregate(
            total=Coalesce(
                Sum(
                    Case(
                        When(direction=Direction.DR, then=F("net_weight_g")),
                        default=-F("net_weight_g"),
                        output_field=DecimalField(max_digits=14, decimal_places=3),
                    )
                ),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=14, decimal_places=3),
            )
        )
        return (self.opening_gold_g + agg["total"]).quantize(GRAM_QUANT)

    def cash_balance(self):
        """Signed net cash balance in NPR (+Dr / -Cr)."""
        agg = self.cash_entries.aggregate(
            total=Coalesce(
                Sum(
                    Case(
                        When(direction=Direction.DR, then=F("amount_npr")),
                        default=-F("amount_npr"),
                        output_field=DecimalField(max_digits=16, decimal_places=2),
                    )
                ),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            )
        )
        return self.opening_cash_npr + agg["total"]


class Order(AuthoredModel):
    """A (usually numbered) job: gold issued to a karigar to make an ornament.

    ``order_number`` is entered manually, is optional, and is NOT unique —
    entries may share or omit it. It is indexed for search.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    shop = models.ForeignKey("accounts.Shop", on_delete=models.CASCADE, related_name="orders")
    order_number = models.CharField(max_length=60, blank=True, null=True, db_index=True)
    karigar = models.ForeignKey(KarigarProfile, on_delete=models.PROTECT, related_name="orders")
    ornament = models.ForeignKey(
        Ornament, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    remarks = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number or f"Order #{self.pk}"

    def net_issued(self):
        return self.gold_entries.filter(direction=Direction.DR).aggregate(
            t=Coalesce(Sum("net_weight_g"), Value(Decimal("0")),
                       output_field=DecimalField(max_digits=14, decimal_places=3))
        )["t"]

    def net_received(self):
        return self.gold_entries.filter(direction=Direction.CR).aggregate(
            t=Coalesce(Sum("net_weight_g"), Value(Decimal("0")),
                       output_field=DecimalField(max_digits=14, decimal_places=3))
        )["t"]

    def wastage(self):
        """Net issued − net received (grams). Positive = gold still out / lost."""
        return (self.net_issued() - self.net_received()).quantize(GRAM_QUANT)


class GoldEntry(AuthoredModel):
    """A single gold movement to/from a karigar.

    ``net_weight_g`` is computed from gross + carat and **stored** so historical
    values survive even if constants change. It is recomputed on every save.
    """

    shop = models.ForeignKey("accounts.Shop", on_delete=models.CASCADE, related_name="gold_entries")
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="gold_entries"
    )
    karigar = models.ForeignKey(
        KarigarProfile, on_delete=models.PROTECT, related_name="gold_entries"
    )
    direction = models.CharField(max_length=2, choices=Direction.choices)
    gross_weight_g = models.DecimalField(
        max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    carat = models.PositiveSmallIntegerField(choices=CARAT_CHOICES)
    net_weight_g = models.DecimalField(max_digits=12, decimal_places=3, editable=False)

    # Receipts (Cr) capture what came back.
    ornament = models.ForeignKey(
        Ornament, on_delete=models.SET_NULL, null=True, blank=True, related_name="gold_entries"
    )
    photo = models.ImageField(upload_to="ornaments/", blank=True, null=True)
    remarks = models.TextField(blank=True)
    entry_date = models.DateField(db_index=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        indexes = [
            models.Index(fields=["karigar", "direction"]),
            models.Index(fields=["shop", "entry_date"]),
        ]

    def save(self, *args, **kwargs):
        # Always recompute net weight from gross + carat.
        self.net_weight_g = compute_net_weight(self.gross_weight_g, self.carat)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_direction_display()} {self.net_weight_g}g ({self.carat}kt)"


class CashEntry(AuthoredModel):
    """A single cash movement to/from a karigar (advances / payments)."""

    shop = models.ForeignKey("accounts.Shop", on_delete=models.CASCADE, related_name="cash_entries")
    karigar = models.ForeignKey(
        KarigarProfile, on_delete=models.PROTECT, related_name="cash_entries"
    )
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_entries"
    )
    direction = models.CharField(max_length=2, choices=Direction.choices)
    amount_npr = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    remarks = models.TextField(blank=True)
    entry_date = models.DateField(db_index=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        indexes = [
            models.Index(fields=["karigar", "direction"]),
            models.Index(fields=["shop", "entry_date"]),
        ]

    def __str__(self):
        return f"{self.get_direction_display()} NPR {self.amount_npr}"
