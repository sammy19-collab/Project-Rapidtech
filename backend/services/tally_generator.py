"""
Generates Tally-compatible XML import files from reconciled results.
"""

import logging
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from sqlalchemy.orm import Session

from models import BooksEntry, ReconciliationResult

logger = logging.getLogger(__name__)

_RECONCILED_CATEGORIES = ("Exact Match", "Strong Match")


def _format_date(date_str: str) -> str:
    """Convert DD-MM-YYYY to YYYYMMDD for Tally DATE field."""
    if not date_str:
        return ""
    parts = date_str.replace("/", "-").split("-")
    if len(parts) == 3:
        if len(parts[0]) == 4:
            # Already YYYY-MM-DD
            return parts[0] + parts[1].zfill(2) + parts[2].zfill(2)
        # DD-MM-YYYY
        return parts[2] + parts[1].zfill(2) + parts[0].zfill(2)
    return date_str


def _add_ledger_entry(parent: Element, ledger_name: str, amount: float) -> None:
    """Append an ALLLEDGERENTRIES.LIST element."""
    entry = SubElement(parent, "ALLLEDGERENTRIES.LIST")
    SubElement(entry, "LEDGERNAME").text = str(ledger_name)
    SubElement(entry, "AMOUNT").text = str(round(amount, 2))


def _build_voucher(parent: Element, result: ReconciliationResult, books: BooksEntry) -> None:
    """Build a single Purchase VOUCHER XML element."""
    voucher = SubElement(parent, "VOUCHER")
    voucher.set("VCHTYPE", "Purchase")
    voucher.set("ACTION", "Create")

    SubElement(voucher, "DATE").text = _format_date(result.invoice_date or "")
    SubElement(voucher, "VOUCHERNUMBER").text = result.invoice_number or ""
    SubElement(voucher, "PARTYLEDGERNAME").text = result.vendor_name or ""
    SubElement(voucher, "NARRATION").text = books.narration or ""

    taxable = result.taxable_value or 0.0
    cgst = books.cgst or 0.0
    sgst = books.sgst or 0.0
    igst = books.igst or 0.0
    total = round(taxable + cgst + sgst + igst, 2)

    _add_ledger_entry(voucher, "Purchase Account", -taxable)
    if cgst:
        _add_ledger_entry(voucher, "CGST", -cgst)
    if sgst:
        _add_ledger_entry(voucher, "SGST", -sgst)
    if igst:
        _add_ledger_entry(voucher, "IGST", -igst)
    # Creditor entry (positive)
    _add_ledger_entry(voucher, result.vendor_name or "Sundry Creditor", total)


def generate_tally_xml(session_id: int, db: Session, limit: int = None) -> str:
    """
    Fetch reconciled results for the session and produce a Tally XML import string.

    Args:
        session_id: The reconciliation session ID.
        db:         Active SQLAlchemy session.
        limit:      If set, only include the first `limit` vouchers (for preview).

    Returns:
        Formatted XML string.
    """
    query = (
        db.query(ReconciliationResult)
        .filter(
            ReconciliationResult.session_id == session_id,
            ReconciliationResult.match_category.in_(_RECONCILED_CATEGORIES),
            ReconciliationResult.books_entry_id.isnot(None),
        )
    )
    if limit:
        query = query.limit(limit)
    results = query.all()

    # Collect BooksEntry details
    books_map = {}
    if results:
        book_ids = [r.books_entry_id for r in results if r.books_entry_id]
        books_entries = db.query(BooksEntry).filter(BooksEntry.id.in_(book_ids)).all()
        books_map = {b.id: b for b in books_entries}

    # Build XML tree
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
    # Remove the XML declaration line added by toprettyxml
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    return "\n".join(lines)
