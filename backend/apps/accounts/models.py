"""Accounts domain: Shop, custom User with a role field, and the app setting
that controls the display calendar (BS/AD).

KarigarProfile and Ornament (Milestone 2) live in the ledger app.
"""
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
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

    def __str__(self):
        return f"Settings for {self.shop} (calendar={self.calendar_preference})"
