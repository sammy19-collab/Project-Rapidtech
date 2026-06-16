"""
Processes GSTR-2B Excel exports and persists GSTR2BEntry records.
"""

import io
import logging
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from models import GSTR2BEntry
from utils.cleaner import (
    clean_gstin,
    clean_invoice_number,
    generate_validation_keys,
    standardize_date,
    safe_decimal,
)

logger = logging.getLogger(__name__)

# GST portal exact column names (lowercase) and their aliases
_GSTIN_ALIASES = {
    "gstin of supplier", "supplier gstin", "gstin", "gst no",
    "gst number", "supplier_gstin", "gstin_of_supplier",
}
_VENDOR_ALIASES = {
    "supplier name", "trade name", "legal name", "legal_name",
    "trade_name", "supplier_name", "party name", "vendor name", "vendor_name",
}
_INVOICE_NUM_ALIASES = {
    "invoice number", "invoice no", "invoice_number", "invoice_no",
    "bill no", "bill number", "document number", "document no",
}
_INVOICE_DATE_ALIASES = {
    "invoice date", "invoice dt", "invoice_date", "invoice_dt",
    "date", "bill date", "document date",
}
_TAXABLE_ALIASES = {
    "taxable value", "taxable amount", "taxable_value", "taxable_amount",
    "taxable val", "gross value",
}
_IGST_ALIASES = {"integrated tax", "igst", "igst amount", "igst_amount", "integrated tax amount"}
_CGST_ALIASES = {"central tax", "cgst", "cgst amount", "cgst_amount", "central tax amount"}
_SGST_ALIASES = {"state/ut tax", "sgst", "sgst amount", "sgst_amount", "state tax", "utgst"}


def _find_column(df_columns: list, aliases: set) -> Optional[str]:
    for col in df_columns:
        if str(col).strip().lower() in aliases:
            return col
    return None


def _detect_header_row(file_bytes: bytes, sheet_name: str) -> int:
    KEYWORDS = {"gstin of supplier", "supplier gstin", "gstin", "invoice number",
                "invoice no", "taxable value", "supplier name", "trade name"}
    df_raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name,
                           header=None, nrows=15, dtype=str, engine="openpyxl")
    for i, row in df_raw.iterrows():
        vals = {str(v).strip().lower() for v in row if pd.notna(v) and str(v).strip()}
        if vals & KEYWORDS:
            return i
    return 0


def process_gstr2b_file(
    file_bytes: bytes,
    session_id: int,
    db: Session,
    reconciliation_month: str = "",
) -> int:
    """
    Parse a GSTR-2B Excel file, normalize data, generate validation keys,
    and persist GSTR2BEntry rows to the database.

    Returns:
        Number of records saved.
    """
    try:
        xf = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Could not open Excel file: {exc}") from exc

    sheet_name = next(
        (n for n in xf.sheet_names if n.strip().lower() == "2b"),
        xf.sheet_names[0],
    )
    logger.info("GSTR-2B: using sheet '%s'", sheet_name)

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

    cols = list(df.columns)
    vendor_col   = _find_column(cols, _VENDOR_ALIASES)
    gstin_col    = _find_column(cols, _GSTIN_ALIASES)
    inv_num_col  = _find_column(cols, _INVOICE_NUM_ALIASES)
    inv_date_col = _find_column(cols, _INVOICE_DATE_ALIASES)
    taxable_col  = _find_column(cols, _TAXABLE_ALIASES)
    igst_col     = _find_column(cols, _IGST_ALIASES)
    cgst_col     = _find_column(cols, _CGST_ALIASES)
    sgst_col     = _find_column(cols, _SGST_ALIASES)

    logger.info("GSTR-2B columns detected: gstin=%s, inv_num=%s, inv_date=%s, taxable=%s",
                gstin_col, inv_num_col, inv_date_col, taxable_col)

    entries = []
    for _, row in df.iterrows():
        raw_gstin   = row.get(gstin_col) if gstin_col else None
        raw_inv_num = row.get(inv_num_col) if inv_num_col else None
        raw_inv_date = row.get(inv_date_col) if inv_date_col else None
        raw_taxable = row.get(taxable_col) if taxable_col else "0"

        if not raw_inv_num and not raw_gstin:
            continue

        gstin          = clean_gstin(raw_gstin)
        invoice_number = clean_invoice_number(raw_inv_num)
        inv_month, inv_date_obj = standardize_date(raw_inv_date)

        taxable = safe_decimal(raw_taxable)
        igst    = safe_decimal(row.get(igst_col)) if igst_col else safe_decimal(0)
        cgst    = safe_decimal(row.get(cgst_col)) if cgst_col else safe_decimal(0)
        sgst    = safe_decimal(row.get(sgst_col)) if sgst_col else safe_decimal(0)
        total_gst = cgst + sgst + igst

        keys = generate_validation_keys(gstin, invoice_number, raw_inv_date,
                                        taxable, reconciliation_month)

        entries.append(GSTR2BEntry(
            session_id=session_id,
            vendor_name=str(row.get(vendor_col)) if vendor_col and row.get(vendor_col) else None,
            gstin=gstin or None,
            invoice_number=invoice_number or None,
            invoice_date=inv_date_obj,
            invoice_month=inv_month or None,
            filing_month=reconciliation_month or None,
            reconciliation_month=reconciliation_month or None,
            taxable_value=taxable,
            cgst=cgst, sgst=sgst, igst=igst, total_gst=total_gst,
            val1=keys["val1"], val2=keys["val2"], val3=keys["val3"],
            val4=keys["val4"], val5=keys["val5"],
        ))

    db.bulk_save_objects(entries)
    db.commit()
    logger.info("Saved %d GSTR2BEntry records for session %d", len(entries), session_id)
    return len(entries)
