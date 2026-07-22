"""Accounts API (auth, current user, settings, manager management)."""

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from ninja import Router
from ninja.errors import HttpError
from ninja.pagination import paginate
from ninja.throttling import AnonRateThrottle
from ninja_jwt.tokens import RefreshToken

from apps.common.auth import require_owner, require_staff
from apps.common.pagination import DefaultPagination

from .models import AppSetting, CalendarPreference, DateFormat, Role
from .schemas import (
    AccessOut,
    AppSettingPatch,
    AppSettingSchema,
    ChangePasswordIn,
    DetailOut,
    LoginIn,
    ManagerCreateIn,
    ManagerUpdateIn,
    RefreshIn,
    TokenOut,
    UserOut,
)

User = get_user_model()
router = Router(tags=["accounts"])

_login_throttle = [AnonRateThrottle("10/m")]


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["full_name"] = user.full_name
    return str(refresh.access_token), str(refresh)


def _validate_password(raw, user=None):
    try:
        validate_password(raw, user)
    except DjangoValidationError as exc:
        raise HttpError(400, " ".join(exc.messages)) from exc


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@router.post("/login/", auth=None, response=TokenOut, throttle=_login_throttle)
def login(request, payload: LoginIn):
    user = authenticate(username=payload.username, password=payload.password)
    if user is None or not user.is_active:
        raise HttpError(401, "Invalid username or password.")
    access, refresh = _tokens_for(user)
    return {"access": access, "refresh": refresh, "user": user}


@router.post("/refresh/", auth=None, response=AccessOut, throttle=_login_throttle)
def refresh_token(request, payload: RefreshIn):
    try:
        old = RefreshToken(payload.refresh)
    except Exception:
        raise HttpError(401, "Invalid or expired refresh token.") from None
    # Rotate: issue a fresh pair.
    user_id = old.get("user_id")
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if not user:
        raise HttpError(401, "User no longer active.")
    access, refresh = _tokens_for(user)
    return {"access": access, "refresh": refresh}


@router.get("/me/", response=UserOut)
def me(request):
    return request.auth


@router.post("/change-password/", response=DetailOut)
def change_password(request, payload: ChangePasswordIn):
    user = request.auth
    if not user.check_password(payload.old_password):
        raise HttpError(400, "Current password is incorrect.")
    _validate_password(payload.new_password, user)
    user.set_password(payload.new_password)
    user.save(update_fields=["password"])
    return {"detail": "Password updated."}


# ---------------------------------------------------------------------------
# App settings (calendar preference)
# ---------------------------------------------------------------------------
def _get_setting(request):
    setting, _ = AppSetting.objects.get_or_create(
        shop=request.auth.shop, defaults={"calendar_preference": CalendarPreference.BS}
    )
    return setting


@router.get("/settings/", response=AppSettingSchema)
def get_settings(request):
    return _get_setting(request)


@router.patch("/settings/", response=AppSettingSchema)
def update_settings(request, payload: AppSettingPatch):
    require_staff(request)
    data = payload.dict(exclude_unset=True)
    setting = _get_setting(request)
    if "calendar_preference" in data:
        if data["calendar_preference"] not in CalendarPreference.values:
            raise HttpError(400, "calendar_preference must be 'BS' or 'AD'.")
        setting.calendar_preference = data["calendar_preference"]
    if "date_format" in data:
        if data["date_format"] not in DateFormat.values:
            raise HttpError(400, "Invalid date_format.")
        setting.date_format = data["date_format"]
    setting.save()
    return setting


# ---------------------------------------------------------------------------
# Manager management (owner only)
# ---------------------------------------------------------------------------
@router.get("/managers/", response=list[UserOut])
@paginate(DefaultPagination)
def list_managers(request):
    require_owner(request)
    return User.objects.filter(role=Role.MANAGER, shop=request.auth.shop).order_by("username")


@router.post("/managers/", response={201: UserOut})
def create_manager(request, payload: ManagerCreateIn):
    require_owner(request)
    if User.objects.filter(username=payload.username).exists():
        raise HttpError(400, "This username is already taken.")
    _validate_password(payload.password)
    user = User(
        username=payload.username,
        email=payload.email or None,
        full_name=payload.full_name,
        role=Role.MANAGER,
        shop=request.auth.shop,
        is_active=True,
    )
    user.set_password(payload.password)
    user.save()
    return 201, user


def _get_manager(request, manager_id):
    require_owner(request)
    manager = User.objects.filter(
        pk=manager_id, role=Role.MANAGER, shop=request.auth.shop
    ).first()
    if not manager:
        raise HttpError(404, "Manager not found.")
    return manager


@router.get("/managers/{manager_id}/", response=UserOut)
def get_manager(request, manager_id: int):
    return _get_manager(request, manager_id)


@router.patch("/managers/{manager_id}/", response=UserOut)
def update_manager(request, manager_id: int, payload: ManagerUpdateIn):
    manager = _get_manager(request, manager_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(manager, field, value)
    manager.save()
    return manager


@router.post("/managers/{manager_id}/activate/", response=UserOut)
def activate_manager(request, manager_id: int):
    manager = _get_manager(request, manager_id)
    manager.is_active = True
    manager.save(update_fields=["is_active"])
    return manager


@router.post("/managers/{manager_id}/deactivate/", response=UserOut)
def deactivate_manager(request, manager_id: int):
    manager = _get_manager(request, manager_id)
    manager.is_active = False
    manager.save(update_fields=["is_active"])
    return manager
