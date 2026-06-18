"""
Generates Tally-compatible XML import files from reconciled results.
"""

import logging
import uuid
from datetime import date
from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from sqlalchemy.orm import Session

from models import BooksEntry, ReconciliationResult

logger = logging.getLogger(__name__)

_RECONCILED_CATEGORIES = ("Exact Match", "Strong Match")


def _format_tally_date(d) -> str:
    """Return YYYYMMDD string for Tally DATE field from a date object or string."""
    if d is None:
        return ""
    if isinstance(d, date):
        return d.strftime("%Y%m%d")
    # Try to parse DD-MM-YYYY or YYYY-MM-DD strings
    s = str(d).replace("/", "-")
    parts = s.split("-")
    if len(parts) == 3:
        if len(parts[0]) == 4:
            return parts[0] + parts[1].zfill(2) + parts[2].zfill(2)
        return parts[2] + parts[1].zfill(2) + parts[0].zfill(2)
    return s


def _dec(val) -> Decimal:
    try:
        return Decimal(str(val or 0))
    except Exception:
        return Decimal("0")


def _add_ledger_entry(parent: Element, ledger_name: str, amount: Decimal) -> None:
    entry = SubElement(parent, "ALLLEDGERENTRIES.LIST")
    SubElement(entry, "LEDGERNAME").text = str(ledger_name)
    SubElement(entry, "ISDEEMEDPOSITIVE").text = "No" if amount < 0 else "Yes"
    SubElement(entry, "AMOUNT").text = str(amount.quantize(Decimal("0.01")))


def _build_voucher(parent: Element, result: ReconciliationResult, books: BooksEntry) -> None:
    voucher = SubElement(parent, "VOUCHER")
    voucher.set("VCHTYPE", "Purchase")
    voucher.set("ACTION", "Create")

    guid = str(uuid.uuid4())
    SubElement(voucher, "GUID").text = guid
    SubElement(voucher, "DATE").text = _format_tally_date(result.invoice_date)
    SubElement(voucher, "VOUCHERNUMBER").text = result.invoice_number or ""
    SubElement(voucher, "PARTYLEDGERNAME").text = result.vendor_name or "Sundry Creditor"
    SubElement(voucher, "VOUCHERTYPE").text = "Purchase"
    SubElement(voucher, "NARRATION").text = books.narration or ""

    taxable = _dec(result.taxable_value)
    cgst    = _dec(books.cgst)
    sgst    = _dec(books.sgst)
    igst    = _dec(books.igst)
    total   = taxable + cgst + sgst + igst

    # Debit entries (negative in Tally convention for purchase)
    _add_ledger_entry(voucher, books.expense_type or "Purchase Account", -taxable)
    if cgst:
        _add_ledger_entry(voucher, "CGST Input", -cgst)
    if sgst:
        _add_ledger_entry(voucher, "SGST Input", -sgst)
    if igst:
        _add_ledger_entry(voucher, "IGST Input", -igst)
    # Credit entry (creditor — positive)
    _add_ledger_entry(voucher, result.vendor_name or "Sundry Creditor", total)

    # Bill allocation
    bill_alloc = SubElement(voucher, "BILLALLOCATIONS.LIST")
    SubElement(bill_alloc, "NAME").text = result.invoice_number or guid
    SubElement(bill_alloc, "BILLTYPE").text = "New Ref"
    SubElement(bill_alloc, "AMOUNT").text = str(total.quantize(Decimal("0.01")))


def generate_tally_xml(session_id: int, db: Session, limit: int = None, month: str = None, year: str = None) -> str:
    """
    Fetch reconciled results for the session and produce a Tally XML import string.
    """
    query = (
        db.query(ReconciliationResult)
        .filter(
            ReconciliationResult.session_id == session_id,
            ReconciliationResult.match_category.in_(_RECONCILED_CATEGORIES),
            ReconciliationResult.books_entry_id.isnot(None),
        )
    )
    if month:
        query = query.filter(ReconciliationResult.invoice_month == month)
    elif year:
        query = query.filter(ReconciliationResult.invoice_month.like(f"%-{year}"))
    if limit:
        query = query.limit(limit)
    results = query.all()

    books_map = {}
    if results:
        book_ids = [r.books_entry_id for r in results if r.books_entry_id]
        books_entries = db.query(BooksEntry).filter(BooksEntry.id.in_(book_ids)).all()
        books_map = {b.id: b for b in books_entries}

    envelope = Element("ENVELOPE")

    header = SubElement(envelope, "HEADER")
    SubElement(header, "TALLYREQUEST").text = "Import Data"

    body = SubElement(envelope, "BODY")
    import_data = SubElement(body, "IMPORTDATA")

    req_desc = SubElement(import_data, "REQUESTDESC")
    SubElement(req_desc, "REPORTNAME").text = "Vouchers"
    static_vars = SubElement(req_desc, "STATICVARIABLES")
    SubElement(static_vars, "SVCURRENTCOMPANY").text = "RapidTech"

    req_data = SubElement(import_data, "REQUESTDATA")

    for result in results:
        books = books_map.get(result.books_entry_id)
        if not books:
            continue
        tally_msg = SubElement(req_data, "TALLYMESSAGE")
        tally_msg.set("xmlns:UDF", "TallyUDF")
        _build_voucher(tally_msg, result, books)

    raw_xml = tostring(envelope, encoding="unicode")
    pretty = minidom.parseString(raw_xml).toprettyxml(indent="  ", encoding=None)
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    return "\n".join(lines)
