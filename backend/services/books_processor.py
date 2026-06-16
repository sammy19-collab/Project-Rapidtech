"""
Processes the company's purchase books Excel file and persists BooksEntry records.
"""

import io
import logging
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from models import BooksEntry
from utils.cleaner import (
    clean_gstin,
    clean_invoice_number,
    generate_validation_keys,
    standardize_date,
    safe_float,
)

logger = logging.getLogger(__name__)

_VENDOR_ALIASES = {
    "vendor name", "vendor_name", "party name", "party_name",
    "supplier name", "supplier_name", "name", "creditor name",
}
_GSTIN_ALIASES = {
    "gstin", "gst no", "gst_no", "gstin no", "gstin number",
    "gstin of supplier", "gst number", "party gstin",
}
_INVOICE_NUM_ALIASES = {
    "invoice number", "invoice_number", "invoice no", "invoice_no",
    "bill no", "bill_no", "bill number", "bill_number",
    "voucher no", "voucher number", "ref no", "reference number",
}
_INVOICE_DATE_ALIASES = {
    "invoice date", "invoice_date", "date", "bill date", "bill_date",
    "voucher date", "transaction date", "inv date",
}
_TAXABLE_ALIASES = {
    "taxable value", "taxable_value", "taxable amount", "taxable_amount",
    "base amount", "base_amount", "assessable value", "taxable",
}
_CGST_ALIASES = {"cgst", "cgst amount", "cgst_amount", "central tax"}
_SGST_ALIASES = {"sgst", "sgst amount", "sgst_amount", "state tax", "state/ut tax"}
_IGST_ALIASES = {"igst", "igst amount", "igst_amount", "integrated tax"}
_EXPENSE_TYPE_ALIASES = {"expense type", "expense_type", "type", "category"}
_NARRATION_ALIASES = {
    "narration", "description", "remarks", "particulars", "details", "note", "notes",
}


def _find_column(df_columns: list, aliases: set) -> Optional[str]:
    """Return the first DataFrame column whose lower-stripped name is in aliases."""
    for col in df_columns:
        if str(col).strip().lower() in aliases:
            return col
    return None


def process_books_file(file_bytes: bytes, session_id: int, db: Session) -> int:
    """
    Parse an Excel file (sheet 'Books'), normalize data, generate validation keys,
    and persist BooksEntry rows to the database.

    Returns:
        Number of records saved.
    Raises:
        ValueError: If the 'Books' sheet is not found.
    """
    try:
        xf = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Could not open Excel file: {exc}") from exc

    sheet_name = None
    for name in xf.sheet_names:
        if name.strip().lower() == "books":
            sheet_name = name
            break
    if sheet_name is None:
        sheet_name = xf.sheet_names[0]   # fall back to first sheet
        logger.info("Sheet 'Books' not found; using first sheet '%s'", sheet_name)

    df = xf.parse(sheet_name, dtype=str)
    df.fillna("", inplace=True)
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    df.replace("", None, inplace=True)
    df.dropna(how="all", inplace=True)
    df.drop_duplicates(inplace=True)
    df.reset_index(drop=True, inplace=True)

    cols = list(df.columns)
    vendor_col = _find_column(cols, _VENDOR_ALIASES)
    gstin_col = _find_column(cols, _GSTIN_ALIASES)
    inv_num_col = _find_column(cols, _INVOICE_NUM_ALIASES)
    inv_date_col = _find_column(cols, _INVOICE_DATE_ALIASES)
    taxable_col = _find_column(cols, _TAXABLE_ALIASES)
    cgst_col = _find_column(cols, _CGST_ALIASES)
    sgst_col = _find_column(cols, _SGST_ALIASES)
    igst_col = _find_column(cols, _IGST_ALIASES)
    expense_col = _find_column(cols, _EXPENSE_TYPE_ALIASES)
    narration_col = _find_column(cols, _NARRATION_ALIASES)

    entries = []
    for _, row in df.iterrows():
        raw_gstin = row[gstin_col] if gstin_col else None
        raw_inv_num = row[inv_num_col] if inv_num_col else None
        raw_inv_date = row[inv_date_col] if inv_date_col else None
        raw_taxable = row[taxable_col] if taxable_col else "0"

        gstin = clean_gstin(raw_gstin)
        invoice_number = clean_invoice_number(raw_inv_num)
        _, date_str = standardize_date(raw_inv_date)
        invoice_date_str = date_str if date_str else (str(raw_inv_date) if raw_inv_date else "")

        taxable_value = safe_float(raw_taxable)
        cgst = safe_float(row[cgst_col]) if cgst_col else 0.0
        sgst = safe_float(row[sgst_col]) if sgst_col else 0.0
        igst = safe_float(row[igst_col]) if igst_col else 0.0
        total_gst = round(cgst + sgst + igst, 2)

        keys = generate_validation_keys(gstin, invoice_number, raw_inv_date, taxable_value)

        entry = BooksEntry(
            session_id=session_id,
            vendor_name=str(row[vendor_col]) if vendor_col and row[vendor_col] else None,
            gstin=gstin or None,
            invoice_number=invoice_number or None,
            invoice_date=invoice_date_str or None,
            taxable_value=taxable_value,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            total_gst=total_gst,
            expense_type=str(row[expense_col]) if expense_col and row[expense_col] else None,
            narration=str(row[narration_col]) if narration_col and row[narration_col] else None,
            val1=keys["val1"],
            val2=keys["val2"],
            val3=keys["val3"],
            val4=keys["val4"],
            val5=keys["val5"],
        )
        entries.append(entry)

    db.bulk_save_objects(entries)
    db.commit()
    logger.info("Saved %d BooksEntry records for session %d", len(entries), session_id)
    return len(entries)
