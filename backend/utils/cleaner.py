import re
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
    if not val or str(val).strip().lower() in ("nan", "none", ""):
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(val).strip().upper())


def standardize_date(date_val):
    if not date_val or str(date_val).strip().lower() in ("nan", "none", "nat", ""):
        return "", ""
    try:
        if isinstance(date_val, (int, float)):
            from openpyxl.utils.datetime import from_excel
            dt = from_excel(int(date_val))
        elif hasattr(date_val, "strftime"):
            dt = date_val
        else:
            dt = dateparser.parse(str(date_val), dayfirst=True)
        return dt.strftime("%m%Y"), dt.strftime("%d-%m-%Y")
    except Exception:
        return "", str(date_val)


def round_taxable(val) -> str:
    try:
        return str(round(float(val), 2))
    except Exception:
        return "0.0"


def safe_float(val) -> float:
    try:
        return float(str(val).strip().replace(",", ""))
    except Exception:
        return 0.0


def generate_validation_keys(gstin, invoice_number, invoice_date, taxable_value) -> dict:
    g = clean_gstin(gstin)
    inv = clean_invoice_number(invoice_number)
    inv_strict = clean_invoice_number_strict(invoice_number)
    month_key, _ = standardize_date(invoice_date)
    tv = safe_float(taxable_value)
    tv_rounded = round_taxable(tv)
    return {
        "val1": g + inv + month_key + str(tv),
        "val2": g + inv + month_key + tv_rounded,
        "val3": g + inv_strict + month_key + tv_rounded,
        "val4": g + month_key + tv_rounded,
        "val5": g + tv_rounded,
    }
