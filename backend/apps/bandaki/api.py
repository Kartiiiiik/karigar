"""Bandaki API: gold-loan customers and loans. **Owner-only** throughout.

Interest and totals are computed dynamically at serialisation time (see
``schemas.BandakiLoanOut``), so the numbers are always current on read.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from ninja.pagination import paginate

from apps.common.auth import require_owner
from apps.common.pagination import DefaultPagination
from apps.ledger.history import build_changelog
from apps.ledger.models import CARAT_CHOICES, Ornament

from .models import (
    BandakiCustomer,
    BandakiItem,
    BandakiLoan,
    BandakiPayment,
    InterestPeriod,
    settle,
)
from .schemas import (
    BandakiCustomerIn,
    BandakiCustomerOut,
    BandakiCustomerPatch,
    BandakiItemIn,
    BandakiItemOut,
    BandakiItemPatch,
    BandakiLoanIn,
    BandakiLoanOut,
    BandakiLoanPatch,
    BandakiPaymentIn,
    BandakiPaymentOut,
    BandakiPaymentPatch,
    HistoryOut,
)

CARAT_VALUES = {c for c, _ in CARAT_CHOICES}

router = Router(tags=["bandaki"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _shop(request):
    return request.auth.shop


def _get_or_404(model, request, pk):
    obj = model.objects.filter(shop=_shop(request), pk=pk).first()
    if not obj:
        raise HttpError(404, f"{model.__name__} not found.")
    return obj


def _customer_in_shop(request, customer_id):
    customer = BandakiCustomer.objects.filter(shop=_shop(request), pk=customer_id).first()
    if not customer:
        raise HttpError(400, "Unknown bandaki customer.")
    return customer


def _validate_period(period):
    if period is not None and period not in InterestPeriod.values:
        raise HttpError(400, "Interest period must be 'monthly' or 'yearly'.")


def _loan_with_payments(request, lid):
    """A loan with its repayments and pledged items prefetched — every derived
    figure needs them, so fetching them separately just costs queries."""
    loan = (
        BandakiLoan.objects.select_related("customer")
        .prefetch_related("payments", "items__ornament")
        .filter(shop=_shop(request), pk=lid)
        .first()
    )
    if not loan:
        raise HttpError(404, "BandakiLoan not found.")
    return loan


def _validate_item(request, data):
    """Shared checks for a pledged piece. Returns the resolved ornament."""
    ornament = None
    if data.get("ornament") is not None:
        ornament = Ornament.objects.filter(shop=_shop(request), pk=data["ornament"]).first()
        if not ornament:
            raise HttpError(400, "Unknown ornament.")
    if data.get("carat") is not None and data["carat"] not in CARAT_VALUES:
        raise HttpError(400, "Carat must be 22 or 24.")
    if data.get("quantity") is not None and data["quantity"] < 1:
        raise HttpError(400, "Quantity must be at least 1.")
    if data.get("gross_weight_g") is not None and data["gross_weight_g"] <= 0:
        raise HttpError(400, "Gross weight must be greater than zero.")
    return ornament


def _reject_overpayment(loan, payments, candidate):
    """Refuse a repayment that pays more than the loan owes.

    Checked against the *whole replayed timeline* rather than today's balance,
    so a back-dated payment slotted in behind later ones is caught too. The
    other payments are already known good, so any surplus belongs to
    ``candidate`` — which is what the message quotes back.
    """
    s = settle(
        loan.gross_amount, loan.interest_rate, loan.interest_period,
        loan.loan_date, payments, timezone.localdate(),
    )
    if s.overpaid > 0:
        room = (Decimal(str(candidate.amount)) - s.overpaid).quantize(Decimal("0.01"))
        raise HttpError(
            400,
            f"That is NPR {s.overpaid} more than this loan owes. "
            f"The most this payment can be is NPR {room}.",
        )
    return s


# ===========================================================================
# Customers (owner only)
# ===========================================================================
@router.get("/bandaki/customers/", response=list[BandakiCustomerOut])
@paginate(DefaultPagination)
def list_customers(request, search: str | None = None):
    require_owner(request)
    qs = BandakiCustomer.objects.filter(shop=_shop(request)).annotate(
        _loan_count=Count("loans")
    )
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(phone__icontains=search)
            | Q(location__icontains=search)
        )
    return qs


@router.post("/bandaki/customers/", response={201: BandakiCustomerOut})
def create_customer(request, payload: BandakiCustomerIn):
    require_owner(request)
    name = payload.name.strip()
    if not name:
        raise HttpError(400, "Customer name is required.")
    customer = BandakiCustomer.objects.create(
        shop=_shop(request),
        name=name,
        phone=payload.phone,
        location=payload.location,
        remarks=payload.remarks,
        created_by=request.auth,
        updated_by=request.auth,
    )
    customer._loan_count = 0
    return 201, customer


@router.get("/bandaki/customers/{cid}/", response=BandakiCustomerOut)
def get_customer(request, cid: int):
    require_owner(request)
    return _get_or_404(BandakiCustomer, request, cid)


@router.patch("/bandaki/customers/{cid}/", response=BandakiCustomerOut)
def update_customer(request, cid: int, payload: BandakiCustomerPatch):
    require_owner(request)
    customer = _get_or_404(BandakiCustomer, request, cid)
    data = payload.dict(exclude_unset=True)
    if "name" in data:
        data["name"] = (data["name"] or "").strip()
        if not data["name"]:
            raise HttpError(400, "Customer name cannot be empty.")
    for f, v in data.items():
        setattr(customer, f, v)
    customer.updated_by = request.auth
    customer.save()
    return customer


@router.get("/bandaki/customers/{cid}/history/", response=list[HistoryOut])
def customer_history(request, cid: int):
    require_owner(request)
    return build_changelog(_get_or_404(BandakiCustomer, request, cid))


# ===========================================================================
# Loans (owner only)
# ===========================================================================
@router.get("/bandaki/loans/", response=list[BandakiLoanOut])
@paginate(DefaultPagination)
def list_loans(request, customer: int | None = None, is_active: bool | None = None,
               search: str | None = None, ordering: str | None = None):
    require_owner(request)
    qs = (
        BandakiLoan.objects.select_related("customer")
        .prefetch_related("payments", "items__ornament")
        .filter(shop=_shop(request))
    )
    if customer:
        qs = qs.filter(customer_id=customer)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if search:
        qs = qs.filter(
            Q(customer__name__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(remarks__icontains=search)
        )
    allowed = {"loan_date", "gross_amount", "interest_rate", "customer__name"}
    if ordering and ordering.lstrip("-") in allowed:
        qs = qs.order_by(ordering, "-created_at")
    else:
        qs = qs.order_by("-loan_date", "-created_at")
    return qs


@router.post("/bandaki/loans/", response={201: BandakiLoanOut})
def create_loan(request, payload: BandakiLoanIn):
    require_owner(request)
    _customer_in_shop(request, payload.customer)
    _validate_period(payload.interest_period)
    # Validate every pledged piece before writing anything, so a bad third item
    # cannot leave a loan behind with two of its three pieces recorded.
    for item in payload.items:
        _validate_item(request, item.dict())

    with transaction.atomic():
        loan = BandakiLoan(
            shop=_shop(request),
            customer_id=payload.customer,
            loan_date=payload.loan_date,
            gross_amount=payload.gross_amount,
            interest_rate=payload.interest_rate,
            interest_period=payload.interest_period,
            remarks=payload.remarks,
            created_by=request.auth,
            updated_by=request.auth,
        )
        loan.save()
        for item in payload.items:
            BandakiItem(
                shop_id=loan.shop_id, loan=loan,
                ornament_id=item.ornament, quantity=item.quantity,
                gross_weight_g=item.gross_weight_g, carat=item.carat,
                description=item.description,
                created_by=request.auth, updated_by=request.auth,
            ).save()
    return 201, _loan_with_payments(request, loan.pk)


@router.get("/bandaki/loans/{lid}/", response=BandakiLoanOut)
def get_loan(request, lid: int):
    require_owner(request)
    return _loan_with_payments(request, lid)


@router.patch("/bandaki/loans/{lid}/", response=BandakiLoanOut)
def update_loan(request, lid: int, payload: BandakiLoanPatch):
    require_owner(request)
    loan = _loan_with_payments(request, lid)
    data = payload.dict(exclude_unset=True)
    if "customer" in data:
        _customer_in_shop(request, data["customer"])
        loan.customer_id = data.pop("customer")
    if "interest_period" in data:
        _validate_period(data["interest_period"])
    for f, v in data.items():
        setattr(loan, f, v)
    # Closing by hand freezes the clock the same way a final payment does;
    # reopening starts it running again.
    if "is_active" in data:
        loan.closed_on = None if loan.is_active else (loan.closed_on or timezone.localdate())
    loan.updated_by = request.auth
    loan.save()
    return loan


@router.get("/bandaki/loans/{lid}/history/", response=list[HistoryOut])
def loan_history(request, lid: int):
    require_owner(request)
    return build_changelog(_get_or_404(BandakiLoan, request, lid))


# ===========================================================================
# Repayments (owner only)
#
# A payment clears accrued byaj first and puts the surplus against the sahu.
# That split is never stored — it is replayed from the whole timeline on every
# read, so correcting or back-dating one payment re-derives all the rest.
# ===========================================================================
def _payment_rows(loan, as_of=None):
    """Loan repayments, each annotated with how it split and what it left."""
    s = settle(
        loan.gross_amount, loan.interest_rate, loan.interest_period,
        loan.loan_date, loan.payments.all(), as_of or timezone.localdate(),
    )
    rows = []
    for line in s.lines:
        p = line.payment
        p.interest_part = str(line.interest_part)
        p.principal_part = str(line.principal_part)
        p.principal_after = str(line.principal_after)
        p.outstanding_after = str(line.outstanding_after)
        rows.append(p)
    return rows


@router.get("/bandaki/loans/{lid}/payments/", response=list[BandakiPaymentOut])
def list_payments(request, lid: int):
    require_owner(request)
    return _payment_rows(_loan_with_payments(request, lid))


@router.post("/bandaki/loans/{lid}/payments/", response={201: BandakiLoanOut})
def create_payment(request, lid: int, payload: BandakiPaymentIn):
    """Record cash received against a loan. Returns the *loan*, re-settled, so
    the caller sees the new balance without a second round trip."""
    require_owner(request)
    loan = _loan_with_payments(request, lid)
    if payload.amount <= 0:
        raise HttpError(400, "Payment amount must be greater than zero.")
    if payload.payment_date < loan.loan_date:
        raise HttpError(400, "A payment cannot predate the loan.")

    candidate = BandakiPayment(
        shop_id=loan.shop_id, loan=loan,
        payment_date=payload.payment_date, amount=payload.amount,
    )
    _reject_overpayment(loan, [*loan.payments.all(), candidate], candidate)

    with transaction.atomic():
        candidate.remarks = payload.remarks
        candidate.created_by = request.auth
        candidate.updated_by = request.auth
        candidate.save()
        loan = _loan_with_payments(request, lid)  # refetch: prefetch cache is stale
        loan.sync_closure(request.auth)
    return 201, loan


@router.patch("/bandaki/payments/{pid}/", response=BandakiLoanOut)
def update_payment(request, pid: int, payload: BandakiPaymentPatch):
    require_owner(request)
    payment = _get_or_404(BandakiPayment, request, pid)
    loan = _loan_with_payments(request, payment.loan_id)
    data = payload.dict(exclude_unset=True)
    for f, v in data.items():
        setattr(payment, f, v)
    if payment.amount <= 0:
        raise HttpError(400, "Payment amount must be greater than zero.")
    if payment.payment_date < loan.loan_date:
        raise HttpError(400, "A payment cannot predate the loan.")

    others = [p for p in loan.payments.all() if p.pk != payment.pk]
    _reject_overpayment(loan, [*others, payment], payment)

    with transaction.atomic():
        payment.updated_by = request.auth
        payment.save()
        loan = _loan_with_payments(request, loan.pk)
        loan.sync_closure(request.auth)
    return loan


@router.delete("/bandaki/payments/{pid}/", response=BandakiLoanOut)
def delete_payment(request, pid: int):
    """Remove a repayment. If that leaves the loan owing again it reopens."""
    require_owner(request)
    payment = _get_or_404(BandakiPayment, request, pid)
    lid = payment.loan_id
    with transaction.atomic():
        payment.delete()
        loan = _loan_with_payments(request, lid)
        loan.sync_closure(request.auth)
    return loan


@router.get("/bandaki/payments/{pid}/history/", response=list[HistoryOut])
def payment_history(request, pid: int):
    require_owner(request)
    return build_changelog(_get_or_404(BandakiPayment, request, pid))


# ===========================================================================
# Pledged gold (owner only)
#
# The customer's own metal, held as security. Pieces are released one at a
# time, so a part-payment can buy back a single bangle while the rest stays.
# ===========================================================================
@router.get("/bandaki/loans/{lid}/items/", response=list[BandakiItemOut])
def list_items(request, lid: int):
    require_owner(request)
    return _loan_with_payments(request, lid).items.all()


@router.post("/bandaki/loans/{lid}/items/", response={201: BandakiLoanOut})
def add_item(request, lid: int, payload: BandakiItemIn):
    """Pledge another piece against an existing loan."""
    require_owner(request)
    loan = _loan_with_payments(request, lid)
    _validate_item(request, payload.dict())
    BandakiItem(
        shop_id=loan.shop_id, loan=loan,
        ornament_id=payload.ornament, quantity=payload.quantity,
        gross_weight_g=payload.gross_weight_g, carat=payload.carat,
        description=payload.description,
        created_by=request.auth, updated_by=request.auth,
    ).save()
    return 201, _loan_with_payments(request, lid)


@router.patch("/bandaki/items/{iid}/", response=BandakiLoanOut)
def update_item(request, iid: int, payload: BandakiItemPatch):
    """Correct a piece's details, or hand it back by setting ``returned_on``."""
    require_owner(request)
    item = _get_or_404(BandakiItem, request, iid)
    data = payload.dict(exclude_unset=True)
    _validate_item(request, data)
    if data.get("returned_on") and data["returned_on"] < item.loan.loan_date:
        raise HttpError(400, "A piece cannot be returned before the loan was taken.")
    for f, v in data.items():
        setattr(item, f, v)
    item.updated_by = request.auth
    item.save()
    return _loan_with_payments(request, item.loan_id)


@router.delete("/bandaki/items/{iid}/", response=BandakiLoanOut)
def delete_item(request, iid: int):
    """Remove a piece recorded in error. Returning gold is a ``returned_on``
    date, not a deletion — that keeps the record of what was held."""
    require_owner(request)
    item = _get_or_404(BandakiItem, request, iid)
    lid = item.loan_id
    item.delete()
    return _loan_with_payments(request, lid)


@router.get("/bandaki/items/{iid}/history/", response=list[HistoryOut])
def item_history(request, iid: int):
    require_owner(request)
    return build_changelog(_get_or_404(BandakiItem, request, iid))
