"""Backend subscription gate: expired shops are blocked on data endpoints but
can still authenticate and read status/profile. Superusers are never gated."""
import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import Subscription

KARIGARS = "/api/v1/karigars/"
STATUS = "/api/v1/subscription/status"
ME = "/api/v1/auth/me/"
LOGIN = "/api/v1/auth/login/"


def _expire(shop):
    today = timezone.localdate()
    Subscription.objects.update_or_create(
        shop=shop,
        defaults={
            "start_date": today - datetime.timedelta(days=60),
            "end_date": today - datetime.timedelta(days=1),  # ended yesterday
        },
    )


# --- expired shop is blocked on data endpoints --------------------------------
@pytest.mark.django_db
def test_expired_shop_blocks_data_endpoint(api, manager, shop):
    _expire(shop)
    resp = api(manager).get(KARIGARS)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SUBSCRIPTION_EXPIRED"


@pytest.mark.django_db
def test_expired_shop_blocks_writes(api, manager, shop):
    _expire(shop)
    resp = api(manager).post_form(KARIGARS, {"full_name": "Blocked"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SUBSCRIPTION_EXPIRED"


# --- but auth + status + profile stay open ------------------------------------
@pytest.mark.django_db
def test_expired_shop_can_still_login(api, manager, shop):
    _expire(shop)
    resp = api().post(LOGIN, {"username": "manager", "password": "Karigar@123"})
    assert resp.status_code == 200
    assert resp.json()["access"]


@pytest.mark.django_db
def test_expired_shop_can_read_status(api, manager, shop):
    _expire(shop)
    resp = api(manager).get(STATUS)
    assert resp.status_code == 200
    assert resp.json()["active"] is False


@pytest.mark.django_db
def test_expired_shop_can_read_profile(api, manager, shop):
    _expire(shop)
    resp = api(manager).get(ME)
    assert resp.status_code == 200
    assert resp.json()["username"] == "manager"


# --- active shop works; superuser is never gated ------------------------------
@pytest.mark.django_db
def test_active_shop_allows_data_endpoint(api, manager, shop):
    resp = api(manager).get(KARIGARS)  # shop fixture is active by default
    assert resp.status_code == 200


@pytest.mark.django_db
def test_superuser_bypasses_gate(api, owner, shop):
    _expire(shop)
    # conftest `owner` is is_superuser=True -> exempt from the gate.
    resp = api(owner).get(KARIGARS)
    assert resp.status_code == 200
