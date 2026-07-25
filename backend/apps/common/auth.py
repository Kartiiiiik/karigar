"""Authentication + role helpers for the Ninja API.

``JWTAuth`` (from ninja-jwt) authenticates the Bearer token and sets
``request.auth`` to the User. Role checks are small helpers that raise
HttpError(403); object-level scoping (a karigar seeing only their own rows)
lives in each endpoint's queryset.
"""
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.accounts.models import Role


class SubscriptionExpired(Exception):
    """Raised by the gated auth when the caller's shop subscription is expired.
    Handled centrally (see config.api) -> HTTP 403 with body code
    ``SUBSCRIPTION_EXPIRED``. The frontend keys its lock on that code."""


class SubscriptionGatedJWTAuth(JWTAuth):
    """JWT auth that additionally enforces the shop subscription.

    Authentication still succeeds for expired shops (so login/refresh and the
    explicitly-ungated status/profile endpoints keep working); this only blocks
    the shop-scoped data endpoints that use it as their auth. Platform
    superusers are never gated.
    """

    def authenticate(self, request, token):
        user = super().authenticate(request, token)
        if user is None:
            return None
        if not getattr(user, "is_superuser", False):
            shop = getattr(user, "shop", None)
            if not (shop and shop.subscription_active):
                raise SubscriptionExpired()
        return user


# The global default auth = JWT + subscription gate. Endpoints that must stay
# reachable while a shop is expired (the status + minimal profile) opt into
# ``open_auth`` (authenticated, NOT gated); public endpoints use auth=None.
auth = SubscriptionGatedJWTAuth()
open_auth = JWTAuth()


def require_roles(request, *roles):
    """Raise 403 unless the authenticated user's role is allowed."""
    user = request.auth
    if not user or user.role not in roles:
        raise HttpError(403, "You do not have permission to perform this action.")
    return user


def require_staff(request):
    """Owner or manager only."""
    return require_roles(request, Role.OWNER, Role.MANAGER)


def require_owner(request):
    return require_roles(request, Role.OWNER)


def is_staff(request):
    return getattr(request.auth, "role", None) in (Role.OWNER, Role.MANAGER)
