from datetime import date, datetime
from decimal import Decimal

from ninja import Schema


# ---------------------------------------------------------------------------
# Ornament
# ---------------------------------------------------------------------------
class OrnamentIn(Schema):
    name: str
    description: str = ""
    is_active: bool = True


class OrnamentPatch(Schema):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class OrnamentOut(Schema):
    id: int
    name: str
    description: str = ""
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Karigar
# ---------------------------------------------------------------------------
class KarigarOut(Schema):
    id: int
    username: str | None = None
    password: str | None = None  # plaintext, staff-only endpoints
    email: str | None = None
    full_name: str
    phone: str = ""
    location: str = ""
    photo: str | None = None
    opening_gold_g: Decimal
    opening_cash_npr: Decimal
    joined_date: date | None = None
    is_active: bool
    gold_balance: str
    cash_balance: str
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def resolve_username(obj):
        return obj.user.username

    @staticmethod
    def resolve_password(obj):
        return obj.plain_password or None

    @staticmethod
    def resolve_email(obj):
        return obj.user.email

    @staticmethod
    def resolve_photo(obj):
        return obj.photo.url if obj.photo else None

    @staticmethod
    def resolve_gold_balance(obj):
        mov = getattr(obj, "_gold_mov", None)  # from KarigarQuerySet.with_balances()
        if mov is not None:
            return str(obj.opening_gold_g + mov)
        return str(obj.gold_balance())

    @staticmethod
    def resolve_cash_balance(obj):
        mov = getattr(obj, "_cash_mov", None)
        if mov is not None:
            return str(obj.opening_cash_npr + mov)
        return str(obj.cash_balance())


# Karigar create/update come in as multipart form data (photo upload), so the
# schema fields are consumed via Form(...) in the endpoint.
# username/password are optional: if omitted they are auto-generated from the
# name and the generated password is returned so the manager can share it.
class KarigarCreateForm(Schema):
    full_name: str
    username: str | None = None
    password: str | None = None
    email: str | None = None
    phone: str = ""
    location: str = ""
    opening_gold_g: Decimal = Decimal("0")
    opening_cash_npr: Decimal = Decimal("0")
    joined_date: date | None = None


class KarigarCreateOut(KarigarOut):
    # Plaintext password, returned ONCE on creation so the manager can pass it
    # to the karigar. Never stored or returned again.
    generated_password: str | None = None

    @staticmethod
    def resolve_generated_password(obj):
        return getattr(obj, "generated_password", None)


class KarigarUpdateForm(Schema):
    full_name: str | None = None
    phone: str | None = None
    location: str | None = None
    opening_gold_g: Decimal | None = None
    opening_cash_npr: Decimal | None = None
    joined_date: date | None = None
    is_active: bool | None = None


class SetPasswordIn(Schema):
    new_password: str


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------
class OrderIn(Schema):
    order_number: str | None = None
    karigar: int
    ornament: int | None = None
    status: str = "open"
    remarks: str = ""


class OrderPatch(Schema):
    order_number: str | None = None
    karigar: int | None = None
    ornament: int | None = None
    status: str | None = None
    remarks: str | None = None


class OrderOut(Schema):
    id: int
    order_number: str | None = None
    karigar: int
    karigar_name: str
    ornament: int | None = None
    ornament_name: str | None = None
    status: str
    remarks: str = ""
    net_issued: str
    net_received: str
    wastage: str
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def resolve_karigar(obj):
        return obj.karigar_id

    @staticmethod
    def resolve_karigar_name(obj):
        return obj.karigar.full_name

    @staticmethod
    def resolve_ornament(obj):
        return obj.ornament_id

    @staticmethod
    def resolve_ornament_name(obj):
        return obj.ornament.name if obj.ornament_id else None

    @staticmethod
    def resolve_net_issued(obj):
        v = getattr(obj, "_net_issued", None)  # from OrderQuerySet.with_totals()
        return str(v if v is not None else obj.net_issued())

    @staticmethod
    def resolve_net_received(obj):
        v = getattr(obj, "_net_received", None)
        return str(v if v is not None else obj.net_received())

    @staticmethod
    def resolve_wastage(obj):
        issued = getattr(obj, "_net_issued", None)
        received = getattr(obj, "_net_received", None)
        if issued is not None and received is not None:
            return str(issued - received)
        return str(obj.wastage())


# ---------------------------------------------------------------------------
# Gold entry (multipart: photo upload)
# ---------------------------------------------------------------------------
class GoldEntryForm(Schema):
    karigar: int
    direction: str
    gross_weight_g: Decimal
    carat: int
    entry_date: date
    order: int | None = None
    ornament: int | None = None
    remarks: str = ""


class GoldEntryPatchForm(Schema):
    direction: str | None = None
    gross_weight_g: Decimal | None = None
    carat: int | None = None
    entry_date: date | None = None
    order: int | None = None
    ornament: int | None = None
    remarks: str | None = None


class GoldEntryOut(Schema):
    id: int
    order: int | None = None
    karigar: int
    karigar_name: str
    direction: str
    direction_display: str
    gross_weight_g: Decimal
    carat: int
    net_weight_g: Decimal
    ornament: int | None = None
    ornament_name: str | None = None
    photo: str | None = None
    remarks: str = ""
    entry_date: date
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def resolve_karigar(obj):
        return obj.karigar_id

    @staticmethod
    def resolve_karigar_name(obj):
        return obj.karigar.full_name

    @staticmethod
    def resolve_order(obj):
        return obj.order_id

    @staticmethod
    def resolve_ornament(obj):
        return obj.ornament_id

    @staticmethod
    def resolve_ornament_name(obj):
        return obj.ornament.name if obj.ornament_id else None

    @staticmethod
    def resolve_direction_display(obj):
        return obj.get_direction_display()

    @staticmethod
    def resolve_photo(obj):
        return obj.photo.url if obj.photo else None


# ---------------------------------------------------------------------------
# Cash entry (JSON)
# ---------------------------------------------------------------------------
class CashEntryIn(Schema):
    karigar: int
    direction: str
    amount_npr: Decimal
    entry_date: date
    order: int | None = None
    remarks: str = ""


class CashEntryPatch(Schema):
    direction: str | None = None
    amount_npr: Decimal | None = None
    entry_date: date | None = None
    order: int | None = None
    remarks: str | None = None


class CashEntryOut(Schema):
    id: int
    karigar: int
    karigar_name: str
    order: int | None = None
    direction: str
    direction_display: str
    amount_npr: Decimal
    remarks: str = ""
    entry_date: date
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def resolve_karigar(obj):
        return obj.karigar_id

    @staticmethod
    def resolve_karigar_name(obj):
        return obj.karigar.full_name

    @staticmethod
    def resolve_order(obj):
        return obj.order_id

    @staticmethod
    def resolve_direction_display(obj):
        return obj.get_direction_display()


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
class HistoryChange(Schema):
    field: str
    old: str
    new: str


class HistoryOut(Schema):
    history_id: int
    type: str
    date: datetime
    user: str | None = None
    changes: list[HistoryChange] = []
