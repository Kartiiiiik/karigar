"""User provisioning: shop-required validation + the ensure_superuser bootstrap."""
import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.accounts.models import Role, Shop, User


# --- shop-required validation (enforced on admin forms via full_clean) --------
@pytest.mark.django_db
def test_non_superuser_without_shop_is_invalid():
    user = User(username="noshop", role=Role.OWNER, is_superuser=False)
    user.set_password("Karigar@123")
    with pytest.raises(ValidationError) as exc:
        user.full_clean()
    assert "shop" in exc.value.message_dict


@pytest.mark.django_db
def test_non_superuser_with_shop_is_valid():
    shop = Shop.objects.create(name="Valid Shop")
    user = User(username="hasshop", role=Role.MANAGER, shop=shop, is_superuser=False)
    user.set_password("Karigar@123")
    user.full_clean()  # must not raise


@pytest.mark.django_db
def test_superuser_without_shop_is_valid():
    user = User(username="root", is_superuser=True, is_staff=True)
    user.set_password("Karigar@123")
    user.full_clean()  # platform admin legitimately has no shop


# --- ensure_superuser management command --------------------------------------
@pytest.mark.django_db
def test_ensure_superuser_creates_from_env(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "platform")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "Sup3r@dmin!")
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "p@example.com")
    call_command("ensure_superuser")
    u = User.objects.get(username="platform")
    assert u.is_superuser and u.is_staff
    assert u.shop_id is None  # never subject to the subscription lock
    assert u.check_password("Sup3r@dmin!")


@pytest.mark.django_db
def test_ensure_superuser_is_idempotent(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "platform")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "Sup3r@dmin!")
    call_command("ensure_superuser")
    call_command("ensure_superuser")  # second run must not raise or duplicate
    assert User.objects.filter(username="platform").count() == 1


@pytest.mark.django_db
def test_ensure_superuser_skips_when_env_missing(monkeypatch):
    monkeypatch.delenv("DJANGO_SUPERUSER_USERNAME", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    call_command("ensure_superuser")
    assert not User.objects.filter(is_superuser=True).exists()
