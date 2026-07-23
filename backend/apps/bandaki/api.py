"""Bandaki API: gold-loan customers and loans. **Owner-only** throughout.

Interest and totals are computed dynamically at serialisation time (see
``schemas.BandakiLoanOut``), so the numbers are always current on read.
"""
from django.db.models import Count, Q
from ninja import Router
from ninja.errors import HttpError
from ninja.pagination import paginate

from apps.common.auth import require_owner
from apps.common.pagination import DefaultPagination
from apps.ledger.history import build_changelog

from .models import BandakiCustomer, BandakiLoan, InterestPeriod
from .schemas import (
    BandakiCustomerIn,
    BandakiCustomerOut,
    BandakiCustomerPatch,
    BandakiLoanIn,
    BandakiLoanOut,
    BandakiLoanPatch,
    HistoryOut,
)

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
    qs = BandakiLoan.objects.select_related("customer").filter(shop=_shop(request))
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
    return 201, loan


@router.get("/bandaki/loans/{lid}/", response=BandakiLoanOut)
def get_loan(request, lid: int):
    require_owner(request)
    return _get_or_404(BandakiLoan, request, lid)


@router.patch("/bandaki/loans/{lid}/", response=BandakiLoanOut)
def update_loan(request, lid: int, payload: BandakiLoanPatch):
    require_owner(request)
    loan = _get_or_404(BandakiLoan, request, lid)
    data = payload.dict(exclude_unset=True)
    if "customer" in data:
        _customer_in_shop(request, data["customer"])
        loan.customer_id = data.pop("customer")
    if "interest_period" in data:
        _validate_period(data["interest_period"])
    for f, v in data.items():
        setattr(loan, f, v)
    loan.updated_by = request.auth
    loan.save()
    return loan


@router.get("/bandaki/loans/{lid}/history/", response=list[HistoryOut])
def loan_history(request, lid: int):
    require_owner(request)
    return build_changelog(_get_or_404(BandakiLoan, request, lid))
