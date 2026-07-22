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


def format_date(ad_date, calendar="AD"):
    """Format a ``datetime.date`` in the given calendar.

    AD -> ``2024-02-10``.  BS -> ``27 Magh 2080``.
    """
    if ad_date is None:
        return ""
    if calendar == "BS":
        try:
            bs = nepali_datetime.date.from_datetime_date(ad_date)
            return f"{bs.day} {_BS_MONTHS[bs.month - 1]} {bs.year}"
        except Exception:
            # Out of the conversion table's range — fall back to AD.
            return ad_date.strftime("%Y-%m-%d")
    return ad_date.strftime("%Y-%m-%d")
