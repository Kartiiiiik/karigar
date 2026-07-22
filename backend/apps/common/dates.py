"""Backend date formatting — the server-side counterpart to the frontend's
``formatDate``. Dates are stored in AD; this renders them in the active
calendar (BS/AD) for reports and exports.

Uses ``nepali-datetime`` for BS conversion — no hand-rolled calendar math.
"""
import nepali_datetime

_BS_MONTHS = [
    "Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
    "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra",
]
_AD_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _render(year, month, day, month_name, fmt):
    if fmt == "YMD":
        return f"{year}-{month:02d}-{day:02d}"
    if fmt == "DMY":
        return f"{day:02d}/{month:02d}/{year}"
    if fmt == "MDY":
        return f"{month:02d}/{day:02d}/{year}"
    # DMY_TEXT (default)
    return f"{day} {month_name} {year}"


def format_date(ad_date, calendar="AD", fmt="DMY_TEXT"):
    """Format a ``datetime.date`` in the given calendar and display format.

    Examples (fmt=DMY_TEXT): AD -> ``10 Feb 2024``, BS -> ``27 Magh 2080``.
    """
    if ad_date is None:
        return ""
    if calendar == "BS":
        try:
            bs = nepali_datetime.date.from_datetime_date(ad_date)
            return _render(bs.year, bs.month, bs.day, _BS_MONTHS[bs.month - 1], fmt)
        except Exception:
            pass  # out of range -> fall through to AD
    return _render(ad_date.year, ad_date.month, ad_date.day, _AD_MONTHS[ad_date.month - 1], fmt)
