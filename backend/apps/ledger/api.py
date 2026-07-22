"""Ledger API: karigars, ornaments, orders, gold & cash entries, self-view.

Permissions:
  * Owner/manager: full access within their shop.
  * Karigar: read-only, scoped to their own rows (orders/gold/cash). No access
    to the karigar roster or ornament management.
"""

import re
import secrets

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import CharField, Q, Sum
from django.db.models.functions import Cast
from ninja import File, Form, Router
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja.pagination import paginate

from apps.accounts.models import Role
from apps.common.auth import require_staff
from apps.common.pagination import DefaultPagination

from .history import build_changelog
from .models import CashEntry, Direction, GoldEntry, KarigarProfile, Order, Ornament
from .schemas import (
    CashEntryIn,
    CashEntryOut,
    CashEntryPatch,
    GoldEntryForm,
    GoldEntryOut,
    GoldEntryPatchForm,
    HistoryOut,
    KarigarCreateForm,
    KarigarCreateOut,
    KarigarOut,
    KarigarUpdateForm,
    OrderIn,
    OrderOut,
    OrderPatch,
    OrnamentIn,
    OrnamentOut,
    OrnamentPatch,
    SetPasswordIn,
)

User = get_user_model()
router = Router(tags=["ledger"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _shop(request):
    return request.auth.shop


def _scope(request, qs, karigar_field="karigar"):
    """Restrict to the caller's shop and, for karigars, their own rows."""
    qs = qs.filter(shop=_shop(request))
    if request.auth.role == Role.KARIGAR:
        profile = getattr(request.auth, "karigar_profile", None)
        if profile is None:
            return qs.none()
        return qs.filter(**{karigar_field: profile})
    return qs


def _order_by(qs, ordering, allowed, default):
    if ordering and ordering.lstrip("-") in allowed:
        return qs.order_by(ordering, "-created_at")
    return qs.order_by(default, "-created_at")


GOLD_ORDER_FIELDS = {"entry_date", "gross_weight_g", "net_weight_g", "carat", "ornament__name"}
CASH_ORDER_FIELDS = {"entry_date", "amount_npr"}


def _filter_gold(qs, karigar, direction, carat, order, order_number, date_from, date_to, search):
    if karigar:
        qs = qs.filter(karigar_id=karigar)
    if direction:
        qs = qs.filter(direction=direction)
    if carat:
        qs = qs.filter(carat=carat)
    if order:
        qs = qs.filter(order_id=order)
    if order_number:
        qs = qs.filter(order__order_number__icontains=order_number)
    if date_from:
        qs = qs.filter(entry_date__gte=date_from)
    if date_to:
        qs = qs.filter(entry_date__lte=date_to)
    if search:
        # Amount/weight, ornament, order, remarks. Weights cast to text so a
        # partial number ("18") matches "18.000".
        qs = qs.annotate(
            _gross=Cast("gross_weight_g", CharField()),
            _net=Cast("net_weight_g", CharField()),
        ).filter(
            Q(_gross__icontains=search)
            | Q(_net__icontains=search)
            | Q(ornament__name__icontains=search)
            | Q(order__order_number__icontains=search)
            | Q(remarks__icontains=search)
        )
    return qs


def _filter_cash(qs, karigar, direction, order, date_from, date_to, search):
    if karigar:
        qs = qs.filter(karigar_id=karigar)
    if direction:
        qs = qs.filter(direction=direction)
    if order:
        qs = qs.filter(order_id=order)
    if date_from:
        qs = qs.filter(entry_date__gte=date_from)
    if date_to:
        qs = qs.filter(entry_date__lte=date_to)
    if search:
        qs = qs.annotate(_amt=Cast("amount_npr", CharField())).filter(
            Q(_amt__icontains=search)
            | Q(order__order_number__icontains=search)
            | Q(remarks__icontains=search)
        )
    return qs


def _dr_cr_totals(qs, field):
    """Return (total_dr, total_cr) as strings for the given numeric field."""
    agg = qs.aggregate(
        dr=Sum(field, filter=Q(direction=Direction.DR)),
        cr=Sum(field, filter=Q(direction=Direction.CR)),
    )
    return str(agg["dr"] or 0), str(agg["cr"] or 0)


def _karigar_in_shop(request, karigar_id):
    profile = KarigarProfile.objects.filter(shop=_shop(request), pk=karigar_id).first()
    if not profile:
        raise HttpError(400, "Unknown karigar.")
    return profile


def _generate_username(full_name):
    """Slug from the name (letters/digits only), made unique with a numeric
    suffix. e.g. 'Ram Bahadur' -> 'rambahadur', then 'rambahadur2', …"""
    base = re.sub(r"[^a-z0-9]", "", (full_name or "").lower()) or "karigar"
    candidate, i = base, 1
    while User.objects.filter(username=candidate).exists():
        i += 1
        candidate = f"{base}{i}"
    return candidate


def _generate_password():
    """Readable, URL-safe random password (has letters + digits; passes
    Django's validators)."""
    return secrets.token_urlsafe(9)


# FK fields arrive as integer PKs from the schemas; assign them via ``<field>_id``.
_FK_FIELDS = {"karigar", "order", "ornament"}


def _assign(instance, data):
    for field, value in data.items():
        if field in _FK_FIELDS:
            setattr(instance, f"{field}_id", value)
        else:
            setattr(instance, field, value)
    return instance


# ===========================================================================
# Ornaments (staff only)
# ===========================================================================
@router.get("/ornaments/", response=list[OrnamentOut])
@paginate(DefaultPagination)
def list_ornaments(request, search: str | None = None):
    require_staff(request)
    qs = Ornament.objects.filter(shop=_shop(request))
    if search:
        qs = qs.filter(name__icontains=search)
    return qs


@router.post("/ornaments/", response={201: OrnamentOut})
def create_ornament(request, payload: OrnamentIn):
    require_staff(request)
    if Ornament.objects.filter(shop=_shop(request), name__iexact=payload.name.strip()).exists():
        raise HttpError(400, f'An ornament named "{payload.name}" already exists.')
    ornament = Ornament.objects.create(shop=_shop(request), **payload.dict())
    return 201, ornament


@router.get("/ornaments/{oid}/", response=OrnamentOut)
def get_ornament(request, oid: int):
    require_staff(request)
    return _get_or_404(Ornament, request, oid)


@router.patch("/ornaments/{oid}/", response=OrnamentOut)
def update_ornament(request, oid: int, payload: OrnamentPatch):
    require_staff(request)
    ornament = _get_or_404(Ornament, request, oid)
    data = payload.dict(exclude_unset=True)
    new_name = data.get("name")
    if new_name and Ornament.objects.filter(
        shop=_shop(request), name__iexact=new_name.strip()
    ).exclude(pk=ornament.pk).exists():
        raise HttpError(400, f'An ornament named "{new_name}" already exists.')
    for f, v in data.items():
        setattr(ornament, f, v)
    ornament.save()
    return ornament


def _get_or_404(model, request, pk):
    obj = model.objects.filter(shop=_shop(request), pk=pk).first()
    if not obj:
        raise HttpError(404, f"{model.__name__} not found.")
    return obj


# ===========================================================================
# Karigars (staff only)
# ===========================================================================
@router.get("/karigars/", response=list[KarigarOut])
@paginate(DefaultPagination)
def list_karigars(request, search: str | None = None):
    require_staff(request)
    qs = KarigarProfile.objects.select_related("user").filter(shop=_shop(request))
    if search:
        qs = qs.filter(full_name__icontains=search)
    return qs


@router.post("/karigars/", response={201: KarigarCreateOut})
def create_karigar(request, payload: KarigarCreateForm = Form(...), photo: UploadedFile = File(None)):
    require_staff(request)
    # Username + password auto-generate from the name when not supplied. The
    # plaintext password is returned once so the manager can share it.
    username = (payload.username or "").strip() or _generate_username(payload.full_name)
    if User.objects.filter(username=username).exists():
        raise HttpError(400, f'The username "{username}" is already taken.')
    password = (payload.password or "").strip() or _generate_password()

    with transaction.atomic():
        user = User(
            username=username,
            email=payload.email or None,
            full_name=payload.full_name,
            role=Role.KARIGAR,
            shop=_shop(request),
            is_active=True,
        )
        user.set_password(password)
        user.save()

        profile = KarigarProfile(
            user=user,
            shop=_shop(request),
            full_name=payload.full_name,
            phone=payload.phone,
            location=payload.location,
            opening_gold_g=payload.opening_gold_g,
            opening_cash_npr=payload.opening_cash_npr,
            joined_date=payload.joined_date,
            plain_password=password,
            created_by=request.auth,
            updated_by=request.auth,
        )
        if photo:
            profile.photo = photo
        profile.save()
    # Attach the plaintext password for the one-time create response.
    profile.generated_password = password
    return 201, profile


@router.get("/karigars/{kid}/", response=KarigarOut)
def get_karigar(request, kid: int):
    require_staff(request)
    return _get_or_404(KarigarProfile, request, kid)


@router.patch("/karigars/{kid}/", response=KarigarOut)
def update_karigar(request, kid: int, payload: KarigarUpdateForm):
    # JSON PATCH (Django doesn't parse multipart on PATCH). Photo changes go
    # through the dedicated /photo/ endpoint below.
    require_staff(request)
    profile = _get_or_404(KarigarProfile, request, kid)
    data = payload.dict(exclude_unset=True)
    for f, v in data.items():
        setattr(profile, f, v)
    profile.updated_by = request.auth
    profile.save()
    if "full_name" in data and profile.user.full_name != profile.full_name:
        profile.user.full_name = profile.full_name
        profile.user.save(update_fields=["full_name"])
    return profile


@router.post("/karigars/{kid}/photo/", response=KarigarOut)
def set_karigar_photo(request, kid: int, photo: UploadedFile = File(...)):
    require_staff(request)
    profile = _get_or_404(KarigarProfile, request, kid)
    profile.photo = photo
    profile.updated_by = request.auth
    profile.save()
    return profile


@router.delete("/karigars/{kid}/", response={204: None})
def deactivate_karigar(request, kid: int):
    """Soft delete: deactivate profile + login."""
    require_staff(request)
    profile = _get_or_404(KarigarProfile, request, kid)
    profile.is_active = False
    profile.save(update_fields=["is_active"])
    profile.user.is_active = False
    profile.user.save(update_fields=["is_active"])
    return 204, None


@router.post("/karigars/{kid}/activate/", response=KarigarOut)
def activate_karigar(request, kid: int):
    require_staff(request)
    profile = _get_or_404(KarigarProfile, request, kid)
    profile.is_active = True
    profile.save(update_fields=["is_active"])
    profile.user.is_active = True
    profile.user.save(update_fields=["is_active"])
    return profile


@router.post("/karigars/{kid}/set_password/", response={200: dict})
def set_karigar_password(request, kid: int, payload: SetPasswordIn):
    require_staff(request)
    profile = _get_or_404(KarigarProfile, request, kid)
    profile.user.set_password(payload.new_password)
    profile.user.save(update_fields=["password"])
    profile.plain_password = payload.new_password
    profile.save(update_fields=["plain_password"])
    return 200, {"detail": "Password updated."}


@router.get("/karigars/{kid}/history/", response=list[HistoryOut])
def karigar_history(request, kid: int):
    require_staff(request)
    return build_changelog(_get_or_404(KarigarProfile, request, kid))


# ===========================================================================
# Self view (karigar)
# ===========================================================================
@router.get("/me/karigar/", response=KarigarOut)
def my_profile(request):
    if request.auth.role != Role.KARIGAR:
        raise HttpError(404, "Only karigars have a self profile.")
    profile = getattr(request.auth, "karigar_profile", None)
    if profile is None:
        raise HttpError(404, "No karigar profile found.")
    return profile


# ===========================================================================
# Orders (staff write; karigar read own)
# ===========================================================================
@router.get("/orders/", response=list[OrderOut])
@paginate(DefaultPagination)
def list_orders(request, karigar: int | None = None, status: str | None = None,
                order_number: str | None = None, ornament: int | None = None):
    qs = _scope(request, Order.objects.select_related("karigar", "ornament"))
    if karigar:
        qs = qs.filter(karigar_id=karigar)
    if status:
        qs = qs.filter(status=status)
    if ornament:
        qs = qs.filter(ornament_id=ornament)
    if order_number:
        qs = qs.filter(order_number__icontains=order_number)
    return qs


@router.post("/orders/", response={201: OrderOut})
def create_order(request, payload: OrderIn):
    require_staff(request)
    _karigar_in_shop(request, payload.karigar)
    order = Order(shop=_shop(request), created_by=request.auth, updated_by=request.auth)
    _assign(order, payload.dict())
    order.save()
    return 201, order


@router.get("/orders/{oid}/", response=OrderOut)
def get_order(request, oid: int):
    return _scoped_or_404(request, Order, oid)


@router.patch("/orders/{oid}/", response=OrderOut)
def update_order(request, oid: int, payload: OrderPatch):
    require_staff(request)
    order = _get_or_404(Order, request, oid)
    _assign(order, payload.dict(exclude_unset=True))
    order.updated_by = request.auth
    order.save()
    return order


@router.get("/orders/{oid}/history/", response=list[HistoryOut])
def order_history(request, oid: int):
    return build_changelog(_scoped_or_404(request, Order, oid))


# ===========================================================================
# Gold entries (staff write; karigar read own)
# ===========================================================================
@router.get("/gold-entries/", response=list[GoldEntryOut])
@paginate(DefaultPagination)
def list_gold(request, karigar: int | None = None, direction: str | None = None,
              carat: int | None = None, order: int | None = None,
              order_number: str | None = None, date_from: str | None = None,
              date_to: str | None = None, ordering: str | None = None,
              search: str | None = None):
    qs = _scope(request, GoldEntry.objects.select_related("karigar", "ornament", "order"))
    qs = _filter_gold(qs, karigar, direction, carat, order, order_number, date_from, date_to, search)
    return _order_by(qs, ordering, GOLD_ORDER_FIELDS, "-entry_date")


@router.get("/gold-entries/summary/")
def gold_summary(request, karigar: int | None = None, direction: str | None = None,
                 carat: int | None = None, order: int | None = None,
                 order_number: str | None = None, date_from: str | None = None,
                 date_to: str | None = None, search: str | None = None):
    """Full-filtered-set aggregates so ledger totals stay correct across pages."""
    qs = _scope(request, GoldEntry.objects.all())
    qs = _filter_gold(qs, karigar, direction, carat, order, order_number, date_from, date_to, search)
    dr, cr = _dr_cr_totals(qs, "net_weight_g")
    return {"count": qs.count(), "total_dr": dr, "total_cr": cr}


@router.post("/gold-entries/", response={201: GoldEntryOut})
def create_gold(request, payload: GoldEntryForm = Form(...), photo: UploadedFile = File(None)):
    require_staff(request)
    _karigar_in_shop(request, payload.karigar)
    if payload.direction == Direction.CR and not payload.ornament:
        raise HttpError(400, "Select the ornament received for a Cr (receive) entry.")
    entry = GoldEntry(shop=_shop(request), created_by=request.auth, updated_by=request.auth)
    _assign(entry, payload.dict())
    if photo:
        entry.photo = photo
    entry.save()  # net_weight recomputed in model.save()
    return 201, entry


@router.get("/gold-entries/{eid}/", response=GoldEntryOut)
def get_gold(request, eid: int):
    return _scoped_or_404(request, GoldEntry, eid)


@router.patch("/gold-entries/{eid}/", response=GoldEntryOut)
def update_gold(request, eid: int, payload: GoldEntryPatchForm):
    require_staff(request)
    entry = _get_or_404(GoldEntry, request, eid)
    _assign(entry, payload.dict(exclude_unset=True))
    entry.updated_by = request.auth
    entry.save()  # recomputes net weight
    return entry


@router.post("/gold-entries/{eid}/photo/", response=GoldEntryOut)
def set_gold_photo(request, eid: int, photo: UploadedFile = File(...)):
    require_staff(request)
    entry = _get_or_404(GoldEntry, request, eid)
    entry.photo = photo
    entry.updated_by = request.auth
    entry.save()
    return entry


@router.get("/gold-entries/{eid}/history/", response=list[HistoryOut])
def gold_history(request, eid: int):
    return build_changelog(_scoped_or_404(request, GoldEntry, eid))


# ===========================================================================
# Cash entries (staff write; karigar read own)
# ===========================================================================
@router.get("/cash-entries/", response=list[CashEntryOut])
@paginate(DefaultPagination)
def list_cash(request, karigar: int | None = None, direction: str | None = None,
              order: int | None = None, date_from: str | None = None,
              date_to: str | None = None, ordering: str | None = None,
              search: str | None = None):
    qs = _scope(request, CashEntry.objects.select_related("karigar", "order"))
    qs = _filter_cash(qs, karigar, direction, order, date_from, date_to, search)
    return _order_by(qs, ordering, CASH_ORDER_FIELDS, "-entry_date")


@router.get("/cash-entries/summary/")
def cash_summary(request, karigar: int | None = None, direction: str | None = None,
                 order: int | None = None, date_from: str | None = None,
                 date_to: str | None = None, search: str | None = None):
    qs = _scope(request, CashEntry.objects.all())
    qs = _filter_cash(qs, karigar, direction, order, date_from, date_to, search)
    dr, cr = _dr_cr_totals(qs, "amount_npr")
    return {"count": qs.count(), "total_dr": dr, "total_cr": cr}


@router.post("/cash-entries/", response={201: CashEntryOut})
def create_cash(request, payload: CashEntryIn):
    require_staff(request)
    _karigar_in_shop(request, payload.karigar)
    entry = CashEntry(shop=_shop(request), created_by=request.auth, updated_by=request.auth)
    _assign(entry, payload.dict())
    entry.save()
    return 201, entry


@router.get("/cash-entries/{eid}/", response=CashEntryOut)
def get_cash(request, eid: int):
    return _scoped_or_404(request, CashEntry, eid)


@router.patch("/cash-entries/{eid}/", response=CashEntryOut)
def update_cash(request, eid: int, payload: CashEntryPatch):
    require_staff(request)
    entry = _get_or_404(CashEntry, request, eid)
    _assign(entry, payload.dict(exclude_unset=True))
    entry.updated_by = request.auth
    entry.save()
    return entry


@router.get("/cash-entries/{eid}/history/", response=list[HistoryOut])
def cash_history(request, eid: int):
    return build_changelog(_scoped_or_404(request, CashEntry, eid))


def _scoped_or_404(request, model, pk):
    """Fetch honouring shop + karigar scoping (used for GET/history)."""
    field = "karigar"
    obj = _scope(request, model.objects.all(), field).filter(pk=pk).first()
    if not obj:
        raise HttpError(404, f"{model.__name__} not found.")
    return obj
