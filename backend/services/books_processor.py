import io
import logging
import re
from collections import Counter
from decimal import Decimal
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from models import BooksEntry
from utils.cleaner import clean_gstin, clean_invoice_number, generate_validation_keys, standardize_date, safe_decimal

logger = logging.getLogger(__name__)

_BRANCH_CODES = ["BBSR", "BLR", "HYD", "MUM", "DEL", "CHN", "KOL", "PUN", "AP"]

def detect_branch_from_filename(filename: str) -> str:
    upper = re.sub(r'[^A-Z0-9]', ' ', filename.upper())
    tokens = set(upper.split())
    for code in _BRANCH_CODES:
        if code in tokens:
            return code
    return "Other"

def detect_recon_month_from_entries(entries: list) -> str:
    months = [e.invoice_date.strftime("%Y-%m") for e in entries if e.invoice_date]
    if not months:
        return ""
    return Counter(months).most_common(1)[0][0]

# Exact RapidTech column names (lowercase for matching)
_RAPIDTECH_COLUMNS = {
    "vender name":          "vendor_name",
    "vender gst no.":       "gstin",
    "bill no":              "invoice_number",
    "bill date":            "invoice_date",
    "total base amt":       "taxable_value",
    "cgst amount":          "cgst",
    "sgst/utgst amount":    "sgst",
    "igst amount":          "igst",
    "expense head":         "expense_type",
    "remark":               "narration",
}
_REQUIRED = {"invoice_number", "invoice_date", "taxable_value", "gstin"}

# Fallback aliases so the system still works if someone sends a slightly different file
_FALLBACK_ALIASES = {
    "vendor name": "vendor_name", "vendor_name": "vendor_name",
    "vender_name": "vendor_name",
    "gstin": "gstin", "gst no": "gstin", "vender gstin": "gstin",
    "vendor gstin": "gstin", "vender gst no": "gstin",
    "invoice number": "invoice_number", "invoice no": "invoice_number",
    "bill number": "invoice_number", "bill_no": "invoice_number",
    "invoice date": "invoice_date", "inv date": "invoice_date",
    "date": "invoice_date",
    "taxable value": "taxable_value", "taxable amount": "taxable_value",
    "base amount": "taxable_value", "total base amount": "taxable_value",
    "cgst": "cgst", "central tax": "cgst",
    "sgst": "sgst", "state/ut tax": "sgst", "sgst/utgst amt": "sgst",
    "igst": "igst", "integrated tax": "igst",
    "expense type": "expense_type", "expense_type": "expense_type",
    "narration": "narration", "remarks": "narration", "description": "narration",
}


def _detect_header_row(file_bytes: bytes, sheet_name: str) -> int:
    KEYWORDS = {"bill no", "vender name", "vendor name", "gstin", "total base amt",
                "invoice number", "invoice no", "taxable value"}
    df_raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name,
                           header=None, nrows=15, dtype=str, engine="openpyxl")
    for i, row in df_raw.iterrows():
        vals = {str(v).strip().lower() for v in row if pd.notna(v) and str(v).strip()}
        if vals & KEYWORDS:
            return i
    return 0


def _map_columns(df_columns: list) -> dict:
    """Return {original_col: internal_field} mapping."""
    mapping = {}
    for col in df_columns:
        key = str(col).strip().lower()
        if key in _RAPIDTECH_COLUMNS:
            mapping[col] = _RAPIDTECH_COLUMNS[key]
        elif key in _FALLBACK_ALIASES:
            mapping[col] = _FALLBACK_ALIASES[key]
    return mapping


def process_books_file(file_bytes: bytes, session_id: int, db: Session,
                       reconciliation_month: str = "", filename: str = "") -> tuple:
    try:
        xf = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Could not open Excel file: {exc}")

    sheet_name = next((n for n in xf.sheet_names if n.strip().lower() == "books"), xf.sheet_names[0])
    logger.info("Books: using sheet '%s'", sheet_name)

    header_row = _detect_header_row(file_bytes, sheet_name)
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name,
                       header=header_row, dtype=str, engine="openpyxl")
    df.fillna("", inplace=True)
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    df.replace("", None, inplace=True)
    df.dropna(how="all", inplace=True)
    df.drop_duplicates(inplace=True)
    df.reset_index(drop=True, inplace=True)

    col_map = _map_columns(list(df.columns))
    # Reverse: internal_field -> original_col
    field_col = {v: k for k, v in col_map.items()}

    missing = _REQUIRED - set(field_col.keys())
    if missing:
        raise ValueError(f"RapidTech format invalid: missing columns: {sorted(missing)}")

    logger.info("Books column mapping: %s", field_col)

    entries = []
    for _, row in df.iterrows():
        raw_gstin    = row.get(field_col.get("gstin"))
        raw_inv_num  = row.get(field_col.get("invoice_number"))
        raw_inv_date = row.get(field_col.get("invoice_date"))
        raw_taxable  = row.get(field_col.get("taxable_value"), "0")

        if not raw_inv_num and not raw_gstin:
            continue

        gstin          = clean_gstin(raw_gstin)
        invoice_number = clean_invoice_number(raw_inv_num)
        inv_month, inv_date_obj = standardize_date(raw_inv_date)

        taxable = safe_decimal(raw_taxable)
        cgst    = safe_decimal(row.get(field_col.get("cgst"), "0"))
        sgst    = safe_decimal(row.get(field_col.get("sgst"), "0"))
        igst    = safe_decimal(row.get(field_col.get("igst"), "0"))
        total_gst = cgst + sgst + igst

        keys = generate_validation_keys(gstin, invoice_number, raw_inv_date,
                                        taxable, reconciliation_month)

        vendor_raw = row.get(field_col.get("vendor_name"))
        vendor_raw = str(vendor_raw) if vendor_raw else None
        if vendor_raw and "-" in vendor_raw:
            parts = vendor_raw.rsplit("-", 1)
            if len(parts) == 2 and len(parts[1].strip()) == 15:
                if not gstin:
                    gstin = clean_gstin(parts[1].strip())
                vendor_raw = parts[0].strip()

        entries.append(BooksEntry(
            session_id=session_id,
            vendor_name=vendor_raw,
            gstin=gstin or None,
            invoice_number=invoice_number or None,
            invoice_date=inv_date_obj,
            invoice_month=inv_month or None,
            reconciliation_month=reconciliation_month or None,
            taxable_value=taxable,
            cgst=cgst, sgst=sgst, igst=igst, total_gst=total_gst,
            expense_type=str(row.get(field_col.get("expense_type")) or "") or None,
            narration=str(row.get(field_col.get("narration")) or "") or None,
            val1=keys["val1"], val2=keys["val2"], val3=keys["val3"],
            val4=keys["val4"], val5=keys["val5"],
        ))

    detected_branch = detect_branch_from_filename(filename) if filename else "Other"
    effective_recon_month = reconciliation_month or detect_recon_month_from_entries(entries)

    # Patch validation keys and reconciliation_month now that we know the period
    if not reconciliation_month and effective_recon_month:
        for e in entries:
            keys = generate_validation_keys(
                e.gstin or "", e.invoice_number or "", e.invoice_date,
                e.taxable_value, effective_recon_month,
            )
            e.val1, e.val2, e.val3, e.val4, e.val5 = (
                keys["val1"], keys["val2"], keys["val3"], keys["val4"], keys["val5"]
            )
            e.reconciliation_month = effective_recon_month

    db.bulk_save_objects(entries)
    db.commit()
    logger.info("Saved %d BooksEntry records for session %d (branch=%s recon_month=%s)",
                len(entries), session_id, detected_branch, effective_recon_month)
    return len(entries), detected_branch, effective_recon_month
