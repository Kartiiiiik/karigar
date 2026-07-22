"""Report API: Cash and Gold ledgers, JSON preview + Excel/PDF export."""
from datetime import datetime

from django.http import HttpResponse
from ninja import Router

from apps.common.auth import require_staff

from .exporters import to_excel, to_pdf
from .services import build_cash_report, build_gold_report, report_subtitle

router = Router(tags=["reports"])

_EXCEL_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _serve(report, slug, fmt):
    if fmt == "excel":
        resp = HttpResponse(to_excel(report), content_type=_EXCEL_CT)
        resp["Content-Disposition"] = f'attachment; filename="{slug}-report.xlsx"'
        return resp
    if fmt == "pdf":
        resp = HttpResponse(to_pdf(report), content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{slug}-report.pdf"'
        return resp
    return {
        "title": report["title"],
        "shop": report["shop"].name,
        "calendar": report["calendar"],
        "subtitle": report_subtitle(report),
        "columns": report["columns"],
        "opening_row": report.get("opening_row"),
        "rows": report["rows"],
        "total_row": report.get("total_row"),
        "closing_row": report.get("closing_row"),
        "totals": {k: str(v) for k, v in report["totals"].items()},
    }


@router.get("/reports/gold/")
def gold_report(request, fmt: str = "json", date_from: str | None = None,
                date_to: str | None = None, karigar: int | None = None):
    require_staff(request)
    report = build_gold_report(request.auth.shop, _parse_date(date_from), _parse_date(date_to), karigar)
    return _serve(report, "gold", fmt)


@router.get("/reports/cash/")
def cash_report(request, fmt: str = "json", date_from: str | None = None,
                date_to: str | None = None, karigar: int | None = None):
    require_staff(request)
    report = build_cash_report(request.auth.shop, _parse_date(date_from), _parse_date(date_to), karigar)
    return _serve(report, "cash", fmt)
