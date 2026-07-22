"""Build the Cash and Gold report data structures.

A report is a plain dict the Excel/PDF renderers consume:

    {
      "kind": "gold" | "cash",
      "title": str,
      "shop": Shop,
      "calendar": "BS" | "AD",
      "date_from": date|None, "date_to": date|None,
      "karigar": KarigarProfile|None,
      "columns": [str, ...],
      "rows": [[cell, ...], ...],
      "totals": {"dr": Decimal, "cr": Decimal, "net": Decimal},
    }
"""
from decimal import Decimal

from apps.accounts.models import AppSetting, CalendarPreference
from apps.common.dates import format_date
from apps.ledger.models import CashEntry, Direction, GoldEntry, KarigarProfile


def _calendar_for(shop):
    setting = AppSetting.objects.filter(shop=shop).first()
    return setting.calendar_preference if setting else CalendarPreference.AD


def _apply_range(qs, date_from, date_to):
    if date_from:
        qs = qs.filter(entry_date__gte=date_from)
    if date_to:
        qs = qs.filter(entry_date__lte=date_to)
    return qs


def _resolve_karigar(shop, karigar_id):
    if not karigar_id:
        return None
    return KarigarProfile.objects.filter(shop=shop, pk=karigar_id).first()


def build_gold_report(shop, date_from=None, date_to=None, karigar_id=None):
    """Gold ledger with net weight split into Net Dr / Net Cr columns.

    Columns: Date, Karigar, Order, Gross (g), Carat, Net Dr (g), Net Cr (g),
    Ornament, Remarks. Opening / total / closing render as in-column rows.
    """
    calendar = _calendar_for(shop)
    karigar = _resolve_karigar(shop, karigar_id)

    qs = GoldEntry.objects.filter(shop=shop).select_related("karigar", "ornament", "order")
    if karigar:
        qs = qs.filter(karigar=karigar)
    qs = _apply_range(qs, date_from, date_to).order_by("entry_date", "created_at")

    gross_sum = net_dr = net_cr = Decimal("0")   # column sums (net incl. opening)
    ent_dr = ent_cr = Decimal("0")               # entry-only sums (for tests/compat)

    # Opening balance folded into the Dr or Cr column.
    opening_row = None
    if karigar:
        op = karigar.opening_gold_g
        if op >= 0:
            opening_row = ["Opening", karigar.full_name, "", "", "", f"{op:.3f}", "", "", ""]
            net_dr += op
        else:
            opening_row = ["Opening", karigar.full_name, "", "", "", "", f"{abs(op):.3f}", "", ""]
            net_cr += abs(op)

    rows = []
    for e in qs:
        gross_sum += e.gross_weight_g
        is_dr = e.direction == Direction.DR
        if is_dr:
            net_dr += e.net_weight_g
            ent_dr += e.net_weight_g
        else:
            net_cr += e.net_weight_g
            ent_cr += e.net_weight_g
        rows.append([
            format_date(e.entry_date, calendar),
            e.karigar.full_name,
            e.order.order_number if e.order else "",
            f"{e.gross_weight_g:.3f}",
            f"{e.carat}kt",
            f"{e.net_weight_g:.3f}" if is_dr else "",
            f"{e.net_weight_g:.3f}" if not is_dr else "",
            e.ornament.name if e.ornament else "",
            e.remarks or "",
        ])

    total_row = ["Total", "", "", f"{gross_sum:.3f}", "", f"{net_dr:.3f}", f"{net_cr:.3f}", "", ""]
    closing = net_dr - net_cr
    if closing >= 0:
        closing_row = ["Closing (Dr)", "", "", "", "", f"{closing:.3f}", "", "", ""]
    else:
        closing_row = ["Closing (Cr)", "", "", "", "", "", f"{abs(closing):.3f}", "", ""]

    return {
        "kind": "gold",
        "title": "Gold Ledger Report",
        "shop": shop,
        "calendar": calendar,
        "date_from": date_from,
        "date_to": date_to,
        "karigar": karigar,
        "columns": ["Date", "Karigar", "Order", "Gross (g)", "Carat", "Net Dr (g)", "Net Cr (g)", "Ornament", "Remarks"],
        "opening_row": opening_row,
        "rows": rows,
        "total_row": total_row,
        "closing_row": closing_row,
        "totals": {"dr": ent_dr, "cr": ent_cr, "net": ent_dr - ent_cr, "unit": "g"},
    }


def build_cash_report(shop, date_from=None, date_to=None, karigar_id=None):
    calendar = _calendar_for(shop)
    karigar = _resolve_karigar(shop, karigar_id)

    qs = CashEntry.objects.filter(shop=shop).select_related("karigar", "order")
    if karigar:
        qs = qs.filter(karigar=karigar)
    qs = _apply_range(qs, date_from, date_to).order_by("entry_date", "created_at")

    debit = credit = Decimal("0")       # column sums (incl. opening)
    ent_dr = ent_cr = Decimal("0")      # entry-only sums

    opening_row = None
    if karigar:
        op = karigar.opening_cash_npr
        if op >= 0:
            opening_row = ["Opening", karigar.full_name, f"{op:.2f}", "", ""]
            debit += op
        else:
            opening_row = ["Opening", karigar.full_name, "", f"{abs(op):.2f}", ""]
            credit += abs(op)

    rows = []
    for e in qs:
        is_dr = e.direction == Direction.DR
        if is_dr:
            debit += e.amount_npr
            ent_dr += e.amount_npr
        else:
            credit += e.amount_npr
            ent_cr += e.amount_npr
        rows.append([
            format_date(e.entry_date, calendar),
            e.karigar.full_name,
            f"{e.amount_npr:.2f}" if is_dr else "",
            f"{e.amount_npr:.2f}" if not is_dr else "",
            e.remarks or "",
        ])

    total_row = ["Total", "", f"{debit:.2f}", f"{credit:.2f}", ""]
    closing = debit - credit
    if closing >= 0:
        closing_row = ["Closing (Dr)", "", f"{closing:.2f}", "", ""]
    else:
        closing_row = ["Closing (Cr)", "", "", f"{abs(closing):.2f}", ""]

    return {
        "kind": "cash",
        "title": "Cash Ledger Report",
        "shop": shop,
        "calendar": calendar,
        "date_from": date_from,
        "date_to": date_to,
        "karigar": karigar,
        "columns": ["Date", "Karigar", "Debit (NPR)", "Credit (NPR)", "Remarks"],
        "opening_row": opening_row,
        "rows": rows,
        "total_row": total_row,
        "closing_row": closing_row,
        "totals": {"dr": ent_dr, "cr": ent_cr, "net": ent_dr - ent_cr, "unit": "NPR"},
    }


def report_subtitle(report):
    """Human-readable range + scope line for headers."""
    cal = report["calendar"]
    parts = []
    if report["date_from"] or report["date_to"]:
        frm = format_date(report["date_from"], cal) if report["date_from"] else "start"
        to = format_date(report["date_to"], cal) if report["date_to"] else "today"
        parts.append(f"{frm} → {to}")
    parts.append(report["karigar"].full_name if report["karigar"] else "All karigars")
    parts.append(f"Calendar: {cal}")
    return "  ·  ".join(parts)
