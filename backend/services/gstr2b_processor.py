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

Filename convention: MMYYYY_GSTIN_GSTR2B_DDMMYYYY.xlsx
  e.g. 042024_37AAGCR9169J1ZN_GSTR2B_18062026.xlsx → April 2024 → 2024-04
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

# Month name → number for "Read me" sheet parsing
_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

# Column positions in the GST portal B2B sheet
_C_GSTIN    = 0
_C_VENDOR   = 1
_C_INV_NUM  = 2
_C_INV_DATE = 4
_C_TAXABLE  = 9
_C_IGST     = 10
_C_CGST     = 11
_C_SGST     = 12


def detect_recon_month_from_filename(filename: str) -> str:
    """
    Parse MMYYYY from the GST portal filename convention:
      MMYYYY_GSTIN_GSTR2B_DDMMYYYY.xlsx
    Returns 'YYYY-MM' or '' if not detected.
    """
    stem = re.sub(r'\.xlsx?$', '', filename, flags=re.IGNORECASE)
    parts = stem.split('_')
    # First token should be MMYYYY (6 digits)
    if parts and re.fullmatch(r'\d{6}', parts[0]):
        mm = parts[0][:2]
        yyyy = parts[0][2:]
        if 1 <= int(mm) <= 12 and 2000 <= int(yyyy) <= 2100:
            return f"{yyyy}-{mm}"
    return ""


def _detect_recon_month_from_metadata(file_bytes: bytes) -> str:
    """
    Read the 'Read me' sheet and extract Tax Period + Financial Year.
    Rows (0-indexed): 3=Financial Year, 4=Tax Period, 5=GSTIN
    Returns 'YYYY-MM' or '' if not found.
    """
    try:
        xf = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
        readme = next((n for n in xf.sheet_names if n.strip().lower() in ("read me", "readme")), None)
        if not readme:
            return ""
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=readme,
                           header=None, nrows=10, dtype=str, engine="openpyxl")
        fy_row = tax_period_row = None
        for i, row in df.iterrows():
            label = str(row.iloc[0]).strip().lower() if pd.notna(row.iloc[0]) else ""
            val   = str(row.iloc[2]).strip()          if pd.notna(row.iloc[2]) else ""
            if "financial year" in label:
                fy_row = val          # e.g. "2024-25"
            if "tax period" in label:
                tax_period_row = val  # e.g. "April"
        if fy_row and tax_period_row:
            month_num = _MONTH_MAP.get(tax_period_row.lower())
            fy_start  = fy_row.split("-")[0] if "-" in fy_row else None
            if month_num and fy_start:
                # April-Dec belong to the starting FY year; Jan-Mar to the next
                year = int(fy_start) if int(month_num) >= 4 else int(fy_start) + 1
                return f"{year}-{month_num}"
    except Exception:
        pass
    return ""


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
    for name in xf.sheet_names:
        if name.strip().lower() in ("2b", "sheet1", "data"):
            return name
    return xf.sheet_names[0]


def process_gstr2b_file(
    file_bytes: bytes,
    session_id: int,
    db: Session,
    reconciliation_month: str = "",
    filename: str = "",
) -> int:
    """
    Parse a GSTR-2B Excel file (B2B sheet), normalise data, generate validation
    keys, and persist GSTR2BEntry rows to the database.

    Reconciliation month is resolved in priority order:
      1. Filename pattern (MMYYYY_...)
      2. 'Read me' sheet metadata
      3. Caller-supplied reconciliation_month
    Returns number of records saved.
    """
    # Detect month with priority: filename > metadata > caller-supplied
    effective_recon_month = (
        detect_recon_month_from_filename(filename)
        or _detect_recon_month_from_metadata(file_bytes)
        or reconciliation_month
    )
    logger.info("GSTR-2B: filename=%s detected recon_month=%s", filename, effective_recon_month)

    try:
        xf = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Could not open Excel file: {exc}") from exc

    sheet_name = _pick_sheet(xf)
    logger.info("GSTR-2B: using sheet '%s'", sheet_name)

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

        raw_gstin    = cell(_C_GSTIN)
        raw_vendor   = cell(_C_VENDOR)
        raw_inv_num  = cell(_C_INV_NUM)
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
                                        taxable, effective_recon_month)

        entries.append(GSTR2BEntry(
            session_id=session_id,
            vendor_name=raw_vendor,
            gstin=gstin or None,
            invoice_number=invoice_number or None,
            invoice_date=inv_date_obj,
            invoice_month=inv_month or None,
            filing_month=effective_recon_month or None,
            reconciliation_month=effective_recon_month or None,
            taxable_value=taxable,
            cgst=cgst, sgst=sgst, igst=igst, total_gst=total_gst,
            val1=keys["val1"], val2=keys["val2"], val3=keys["val3"],
            val4=keys["val4"], val5=keys["val5"],
        ))

    db.bulk_save_objects(entries)
    db.commit()
    logger.info("Saved %d GSTR2BEntry records for session %d (recon_month=%s)",
                len(entries), session_id, effective_recon_month)
    return len(entries)
