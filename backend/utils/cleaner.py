import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from dateutil import parser as dateparser


def clean_gstin(val) -> str:
    if not val or str(val).strip().lower() in ("nan", "none", ""):
        return ""
    return re.sub(r"\s+", "", str(val).strip().upper())


def clean_invoice_number(val) -> str:
    if not val or str(val).strip().lower() in ("nan", "none", ""):
        return ""
    return str(val).strip().upper()


def clean_invoice_number_strict(val) -> str:
    """Remove all non-alphanumeric chars. JAC/2024-25/066 → JAC202425066"""
    if not val or str(val).strip().lower() in ("nan", "none", ""):
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(val).strip().upper())


def standardize_date(date_val) -> tuple[str, date | None]:
    """
    Parse any date value and return (MM-YYYY string, date object).
    date object is None if parsing fails.
    """
    if not date_val or str(date_val).strip().lower() in ("nan", "none", "nat", ""):
        return "", None
    try:
        if isinstance(date_val, date):
            dt = date_val
        elif isinstance(date_val, (int, float)):
            from openpyxl.utils.datetime import from_excel
            dt = from_excel(int(date_val)).date()
        else:
            parsed = dateparser.parse(str(date_val), dayfirst=True)
            dt = parsed.date() if parsed else None
        if dt is None:
            return "", None
        month_key = dt.strftime("%m-%Y")   # MM-YYYY
        return month_key, dt
    except Exception:
        return "", None


def safe_decimal(val) -> Decimal:
    """Convert any value to Decimal safely."""
    try:
        s = str(val).strip().replace(",", "")
        if s.lower() in ("nan", "none", ""):
            return Decimal("0")
        return Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, Exception):
        return Decimal("0")


def safe_float(val) -> float:
    try:
        return float(str(val).strip().replace(",", ""))
    except Exception:
        return 0.0


def generate_validation_keys(
    gstin: str,
    invoice_number: str,
    invoice_date,
    taxable_value,
    reconciliation_month: str = "",  # MM-YYYY from upload selection
) -> dict:
    """
    Generate 5 composite validation keys.
    Uses reconciliation_month (filing period) — NOT invoice_month —
    because GSTR-2B groups invoices by filing period, not invoice date.
    """
    g       = clean_gstin(gstin)
    inv     = clean_invoice_number(invoice_number)
    inv_s   = clean_invoice_number_strict(invoice_number)
    tv      = safe_decimal(taxable_value)
    tv_str  = str(tv)
    rm      = reconciliation_month or ""

    return {
        "val1": g + inv  + rm + str(safe_float(taxable_value)),
        "val2": g + inv  + rm + tv_str,
        "val3": g + inv_s + rm + tv_str,
        "val4": g + rm + tv_str,
        "val5": g + tv_str,
    }
