"""Authentication + role helpers for the Ninja API.

``JWTAuth`` (from ninja-jwt) authenticates the Bearer token and sets
``request.auth`` to the User. Role checks are small helpers that raise
HttpError(403); object-level scoping (a karigar seeing only their own rows)
lives in each endpoint's queryset.
"""
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.accounts.models import Role

# The single shared auth instance used across routers.
auth = JWTAuth()


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
