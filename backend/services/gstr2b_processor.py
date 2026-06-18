"""
Processes GSTR-2B Excel exports (GST portal format) and persists GSTR2BEntry records.

The GST portal GSTR-2B file has multiple sheets. We read the 'B2B' sheet which
contains taxable inward supplies from registered persons. The sheet has a
complex 2-row merged header followed by actual data rows. We detect the data
start row by finding the first row whose column-0 value looks like a GSTIN
(15 alphanumeric characters).

B2B column positions (0-indexed):
  0  - GSTIN of supplier
  1  - Trade/Legal name
  2  - Invoice number
  3  - Invoice type
  4  - Invoice date
  5  - Invoice value (total)
  6  - Place of supply
  7  - Reverse charge
  8  - Rate (%)
  9  - Taxable value
  10 - Integrated Tax (IGST)
  11 - Central Tax (CGST)
  12 - State/UT Tax (SGST)
  13 - Cess
  14 - GSTR-1/IFF Period
  15 - Filing date
"""

import io
import logging
import re

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

_GSTIN_RE = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')

# Column positions in the GST portal B2B sheet
_C_GSTIN    = 0
_C_VENDOR   = 1
_C_INV_NUM  = 2
_C_INV_DATE = 4
_C_TAXABLE  = 9
_C_IGST     = 10
_C_CGST     = 11
_C_SGST     = 12


def _find_data_start(df: pd.DataFrame) -> int:
    """Return the first row index whose column-0 looks like a 15-char GSTIN."""
    for i, row in df.iterrows():
        val = str(row.iloc[0]).strip().upper() if pd.notna(row.iloc[0]) else ""
        if _GSTIN_RE.match(val) or (len(val) == 15 and val.isalnum()):
            return i
    return 0


def _pick_sheet(xf: pd.ExcelFile) -> str:
    """Return 'B2B' sheet name (case-insensitive), fall back to first sheet."""
    for name in xf.sheet_names:
        if name.strip().lower() == "b2b":
            return name
    # Try to find any sheet with GST invoice data
    for name in xf.sheet_names:
        if name.strip().lower() in ("2b", "sheet1", "data"):
            return name
    return xf.sheet_names[0]


def process_gstr2b_file(
    file_bytes: bytes,
    session_id: int,
    db: Session,
    reconciliation_month: str = "",
) -> int:
    """
    Parse a GSTR-2B Excel file (B2B sheet), normalise data, generate validation
    keys, and persist GSTR2BEntry rows to the database.

    Returns number of records saved.
    """
    try:
        xf = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Could not open Excel file: {exc}") from exc

    sheet_name = _pick_sheet(xf)
    logger.info("GSTR-2B: using sheet '%s' from %s", sheet_name, list(xf.sheet_names))

    df_raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name,
                           header=None, dtype=str, engine="openpyxl")
    df_raw.fillna("", inplace=True)

    data_start = _find_data_start(df_raw)
    logger.info("GSTR-2B: data starts at row %d", data_start)

    df = df_raw.iloc[data_start:].copy()
    df.reset_index(drop=True, inplace=True)

    entries = []
    for _, row in df.iterrows():
        def cell(pos):
            try:
                v = row.iloc[pos]
                return str(v).strip() if v and str(v).strip() not in ("", "nan") else None
            except IndexError:
                return None

        raw_gstin   = cell(_C_GSTIN)
        raw_vendor  = cell(_C_VENDOR)
        raw_inv_num = cell(_C_INV_NUM)
        raw_inv_date = cell(_C_INV_DATE)
        raw_taxable  = cell(_C_TAXABLE) or "0"
        raw_igst     = cell(_C_IGST) or "0"
        raw_cgst     = cell(_C_CGST) or "0"
        raw_sgst     = cell(_C_SGST) or "0"

        if not raw_gstin and not raw_inv_num:
            continue

        gstin = clean_gstin(raw_gstin)

        # Skip template/instruction rows — real GSTINs are 15 chars
        if gstin and len(gstin) != 15:
            continue

        invoice_number = clean_invoice_number(raw_inv_num)
        inv_month, inv_date_obj = standardize_date(raw_inv_date)

        taxable   = safe_decimal(raw_taxable)
        igst      = safe_decimal(raw_igst)
        cgst      = safe_decimal(raw_cgst)
        sgst      = safe_decimal(raw_sgst)
        total_gst = cgst + sgst + igst

        keys = generate_validation_keys(gstin, invoice_number, raw_inv_date,
                                        taxable, reconciliation_month)

        entries.append(GSTR2BEntry(
            session_id=session_id,
            vendor_name=raw_vendor,
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
