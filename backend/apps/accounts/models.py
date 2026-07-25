"""Accounts domain: Shop, custom User with a role field, and the app setting
that controls the display calendar (BS/AD).

KarigarProfile and Ornament (Milestone 2) live in the ledger app.
"""
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel

from .managers import UserManager


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    MANAGER = "manager", "Manager"
    KARIGAR = "karigar", "Karigar"


class CalendarPreference(models.TextChoices):
    BS = "BS", "Bikram Sambat"
    AD = "AD", "Gregorian (AD)"


class DateFormat(models.TextChoices):
    # Rendered within the active calendar (BS or AD).
    DMY_TEXT = "DMY_TEXT", "27 Magh 2080 (day month year)"
    YMD = "YMD", "2080-10-27 (year-month-day)"
    DMY = "DMY", "27/10/2080 (day/month/year)"
    MDY = "MDY", "10/27/2080 (month/day/year)"


class Shop(TimeStampedModel):
    """The shop entity. Single-shop MVP, modelled so multi-shop is possible
    later without a rewrite."""

    name = models.CharField(max_length=200)
    address = models.CharField(max_length=500, blank=True)
    contact = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def subscription_active(self) -> bool:
        """True only when the shop has a subscription and it is not expired.
        A shop with NO subscription is treated as inactive (locked) — the secure
        default; provisioning always sets one, and the migration backfills
        existing shops."""
        sub = getattr(self, "subscription", None)
        return bool(sub and sub.is_active)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user. Login is by username; email is optional but unique when set.

    ``role`` drives every permission decision in the app.
    """

    username_validator = RegexValidator(
        r"^[\w.@+-]+$",
        "Enter a valid username (letters, digits and @/./+/-/_ only).",
    )

    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[username_validator],
    )
    email = models.EmailField(blank=True, null=True, unique=True)
    full_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.KARIGAR,
        db_index=True,
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return f"{self.username} ({self.role})"

    def clean(self):
        """Every shop-level account (owner/manager/karigar) must belong to a
        shop. Only the platform superuser may have no shop. Enforced on the
        Django admin forms via full_clean(); the API always sets the shop from
        the authenticated user, so it is never trusted from a client payload.
        """
        super().clean()
        if not self.is_superuser and self.shop_id is None:
            raise ValidationError(
                {"shop": "A shop is required for owner/manager/karigar accounts."}
            )

    @property
    def is_owner(self):
        return self.role == Role.OWNER

    @property
    def is_manager(self):
        return self.role == Role.MANAGER

    @property
    def is_karigar(self):
        return self.role == Role.KARIGAR

    @property
    def is_staff_role(self):
        """Owner or manager — the shop-running roles."""
        return self.role in (Role.OWNER, Role.MANAGER)


class Subscription(TimeStampedModel):
    """Admin-controlled subscription for a shop. Exactly one per shop; extending
    means moving ``end_date`` forward (no self-serve billing in the app).

    Expiry is computed on the server in Asia/Kathmandu time: a subscription is
    active while ``today <= end_date`` (the end date is inclusive — the last
    fully-usable day).
    """

    shop = models.OneToOneField(
        Shop,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    start_date = models.DateField()
    end_date = models.DateField(db_index=True)
    plan = models.CharField(max_length=100, blank=True, help_text="Optional label, e.g. 'Monthly', 'Annual'.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["shop__name"]

    def __str__(self):
        return f"{self.shop} — {'active' if self.is_active else 'expired'} until {self.end_date}"

    @property
    def is_active(self) -> bool:
        # timezone.localdate() resolves to settings.TIME_ZONE (Asia/Kathmandu).
        # end_date is None only for an unsaved instance (e.g. the admin's blank
        # "add another" inline row) — treat that as inactive rather than crash.
        if self.end_date is None:
            return False
        return timezone.localdate() <= self.end_date

    @property
    def days_remaining(self) -> int:
        """Whole days until expiry. 0 on the last active day; negative once
        expired."""
        if self.end_date is None:
            return 0
        return (self.end_date - timezone.localdate()).days


class AppSetting(TimeStampedModel):
    """Singleton-style global settings. ``calendar_preference`` controls
    display formatting only; storage is always AD. Editable by owner+manager.
    """

    shop = models.OneToOneField(
        Shop,
        on_delete=models.CASCADE,
        related_name="settings",
    )
    calendar_preference = models.CharField(
        max_length=2,
        choices=CalendarPreference.choices,
        default=CalendarPreference.BS,
    )
    date_format = models.CharField(
        max_length=10,
        choices=DateFormat.choices,
        default=DateFormat.DMY_TEXT,
    )

    def __str__(self):
        return f"Settings for {self.shop} (calendar={self.calendar_preference})"
