"""Subscription model + /subscription/status endpoint."""
import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import Shop, Subscription, User

STATUS = "/api/v1/subscription/status"


def _sub(shop, days):
    """Set the shop's subscription to end `days` from today (negative = already
    expired). Uses update_or_create so it overrides the active subscription the
    conftest `shop` fixture attaches by default."""
    today = timezone.localdate()
    sub, _ = Subscription.objects.update_or_create(
        shop=shop,
        defaults={
            "start_date": today - datetime.timedelta(days=30),
            "end_date": today + datetime.timedelta(days=days),
        },
    )
    return sub


# --- model --------------------------------------------------------------------
@pytest.mark.django_db
def test_subscription_active_and_days_remaining(shop):
    sub = _sub(shop, 10)
    assert sub.is_active is True
    assert sub.days_remaining == 10


@pytest.mark.django_db
def test_subscription_expired(shop):
    sub = _sub(shop, -1)
    assert sub.is_active is False
    assert sub.days_remaining == -1


@pytest.mark.django_db
def test_subscription_active_on_last_day(shop):
    sub = _sub(shop, 0)  # today == end_date is still active (inclusive)
    assert sub.is_active is True


@pytest.mark.django_db
def test_shop_subscription_active_helper(db):
    fresh = Shop.objects.create(name="Subless Shop")  # no subscription attached
    assert fresh.subscription_active is False  # no subscription -> locked default
    _sub(fresh, 5)
    fresh.refresh_from_db()
    assert fresh.subscription_active is True


# --- endpoint -----------------------------------------------------------------
@pytest.mark.django_db
def test_status_endpoint_active(api, manager, shop):
    _sub(shop, 7)
    resp = api(manager).get(STATUS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"] is True
    assert body["days_remaining"] == 7
    assert body["end_date"]


@pytest.mark.django_db
def test_status_endpoint_expired(api, manager, shop):
    _sub(shop, -3)
    resp = api(manager).get(STATUS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"] is False
    assert "ended" in body["message"].lower()


@pytest.mark.django_db
def test_status_endpoint_no_subscription_is_inactive(api, manager):
    Subscription.objects.filter(shop=manager.shop).delete()  # remove fixture default
    resp = api(manager).get(STATUS)
    assert resp.status_code == 200
    assert resp.json()["active"] is False


@pytest.mark.django_db
def test_status_endpoint_superuser_always_active(api, db):
    su = User.objects.create_superuser(username="root2", password="Sup3r@dmin!")
    resp = api(su).get(STATUS)
    assert resp.status_code == 200
    assert resp.json()["active"] is True
