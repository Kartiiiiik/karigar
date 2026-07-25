"""Shared pytest fixtures for the Ninja API.

Auth is exercised end-to-end: each request carries a real JWT (minted via
ninja-jwt) in the Authorization header, driven through Django's test Client.
"""
import datetime
import json
from decimal import Decimal
from urllib.parse import urlencode

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import Role, Shop, Subscription, User
from apps.ledger.models import KarigarProfile, Ornament


def _activate(shop, days=365):
    """Attach an active subscription so shops pass the subscription gate by
    default (mirrors production, where provisioning always sets one). Tests that
    exercise expiry override this via update_or_create."""
    today = timezone.localdate()
    Subscription.objects.create(
        shop=shop,
        start_date=today - datetime.timedelta(days=1),
        end_date=today + datetime.timedelta(days=days),
    )
    return shop


class Api:
    """Thin wrapper over Django's test Client that injects a Bearer token and
    offers JSON / form / query helpers. Responses expose ``.status_code`` and
    ``.json()``."""

    def __init__(self, user=None):
        self.client = Client()
        self.headers = {}
        if user is not None:
            from ninja_jwt.tokens import RefreshToken

            access = RefreshToken.for_user(user).access_token
            self.headers = {"HTTP_AUTHORIZATION": f"Bearer {access}"}

    def get(self, path, params=None):
        return self.client.get(path, params or {}, **self.headers)

    def post(self, path, data=None):
        return self.client.post(path, json.dumps(data or {}),
                                content_type="application/json", **self.headers)

    def patch(self, path, data=None):
        return self.client.patch(path, json.dumps(data or {}),
                                 content_type="application/json", **self.headers)

    def post_form(self, path, data=None):
        # multipart/form-data (Django builds it from the dict).
        return self.client.post(path, data or {}, **self.headers)

    def patch_form(self, path, data=None):
        return self.client.patch(path, urlencode(data or {}),
                                 content_type="application/x-www-form-urlencoded", **self.headers)

    def delete(self, path):
        return self.client.delete(path, **self.headers)


@pytest.fixture
def api():
    return lambda user=None: Api(user)


@pytest.fixture
def shop(db):
    return _activate(Shop.objects.create(name="Test Shop"))


@pytest.fixture
def other_shop(db):
    return _activate(Shop.objects.create(name="Other Shop"))


def _make_user(shop, username, role, **kw):
    u = User(username=username, role=role, shop=shop, full_name=username, **kw)
    u.set_password("Karigar@123")
    u.save()
    return u


@pytest.fixture
def owner(shop):
    return _make_user(shop, "owner", Role.OWNER, is_staff=True, is_superuser=True)


@pytest.fixture
def manager(shop):
    return _make_user(shop, "manager", Role.MANAGER)


@pytest.fixture
def karigar_user(shop):
    return _make_user(shop, "karigar1", Role.KARIGAR)


@pytest.fixture
def other_karigar_user(shop):
    return _make_user(shop, "karigar2", Role.KARIGAR)


@pytest.fixture
def karigar_profile(shop, karigar_user):
    return KarigarProfile.objects.create(
        user=karigar_user, shop=shop, full_name="Ram",
        opening_gold_g=Decimal("5.000"), opening_cash_npr=Decimal("0.00"),
        joined_date=datetime.date(2024, 1, 1),
    )


@pytest.fixture
def other_karigar_profile(shop, other_karigar_user):
    return KarigarProfile.objects.create(
        user=other_karigar_user, shop=shop, full_name="Sita",
    )


@pytest.fixture
def ornament(shop):
    return Ornament.objects.create(shop=shop, name="Chain")
