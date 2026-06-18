"""
Core reconciliation engine: O(n) hash-based matching of BooksEntry against
GSTR2BEntry rows using five composite validation keys.

Books stores LINE ITEMS (multiple rows per invoice); GSTR-2B stores INVOICE
TOTALS (one row per invoice). We aggregate Books line items by
(gstin, invoice_number) before matching so amounts compare correctly.
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from models import AuditLog, BooksEntry, GSTR2BEntry, ReconciliationResult, ReconciliationSession
from utils.cleaner import generate_validation_keys

logger = logging.getLogger(__name__)

_MATCH_KEYS = ["val1", "val2", "val3", "val4", "val5"]

_CAT_EXACT         = "Exact Match"
_CAT_STRONG        = "Strong Match"
_CAT_PROBABLE      = "Probable Match"
_CAT_MANUAL        = "Manual Review"
_CAT_MISSING_BOOKS = "Missing in Books"

_D0 = Decimal("0")


class _AggBooks:
    """Aggregated Books invoice — sums all line items for one GSTIN+invoice."""
    __slots__ = (
        "id", "all_ids", "vendor_name", "gstin", "invoice_number",
        "invoice_date", "invoice_month", "reconciliation_month",
        "taxable_value", "cgst", "sgst", "igst", "total_gst",
        "val1", "val2", "val3", "val4", "val5",
    )

    def __init__(self, entries: List[BooksEntry]):
        first = entries[0]
        self.id             = first.id
        self.all_ids        = [e.id for e in entries]
        self.vendor_name    = first.vendor_name
        self.gstin          = first.gstin
        self.invoice_number = first.invoice_number
        self.invoice_date   = first.invoice_date
        self.invoice_month  = first.invoice_month
        self.reconciliation_month = first.reconciliation_month

        self.taxable_value = sum((e.taxable_value or _D0) for e in entries)
        self.cgst          = sum((e.cgst          or _D0) for e in entries)
        self.sgst          = sum((e.sgst          or _D0) for e in entries)
        self.igst          = sum((e.igst          or _D0) for e in entries)
        self.total_gst     = self.cgst + self.sgst + self.igst

        # Re-compute validation keys with aggregated totals
        inv_date_str = str(self.invoice_date) if self.invoice_date else ""
        keys = generate_validation_keys(
            self.gstin, self.invoice_number,
            inv_date_str, self.taxable_value,
            self.reconciliation_month or "",
        )
        self.val1 = keys["val1"]
        self.val2 = keys["val2"]
        self.val3 = keys["val3"]
        self.val4 = keys["val4"]
        self.val5 = keys["val5"]


def _category_for_score(score: int) -> str:
    if score == 5: return _CAT_EXACT
    if score == 4: return _CAT_STRONG
    if score in (2, 3): return _CAT_PROBABLE
    return _CAT_MANUAL


def _mismatch_reason(score: int, b: _AggBooks, g: Optional[GSTR2BEntry]) -> Optional[str]:
    if score == 5:
        return None
    if g is None:
        return "No matching invoice found in GSTR-2B"
    reasons = []
    if (b.gstin or "") != (g.gstin or ""):
        reasons.append("GSTIN mismatch")
    if (b.invoice_number or "") != (g.invoice_number or ""):
        reasons.append("Invoice number mismatch")
    if b.invoice_date != g.invoice_date:
        reasons.append("Invoice date mismatch")
    if abs((b.taxable_value or _D0) - (g.taxable_value or _D0)) > Decimal("1.00"):
        reasons.append(f"Taxable value mismatch (Books:{b.taxable_value} vs GSTR:{g.taxable_value})")
    return "; ".join(reasons) if reasons else "Partial key mismatch"


def run_reconciliation(session_id: int, db: Session) -> dict:
    """
    Aggregate Books line items per invoice, then O(n) hash-match against GSTR-2B.
    One-to-one: each GSTR-2B entry is matched at most once.
    """
    db.query(ReconciliationResult).filter(
        ReconciliationResult.session_id == session_id
    ).delete(synchronize_session=False)
    db.flush()

    raw_books: List[BooksEntry] = (
        db.query(BooksEntry).filter(BooksEntry.session_id == session_id).all()
    )
    gstr2b: List[GSTR2BEntry] = (
        db.query(GSTR2BEntry).filter(GSTR2BEntry.session_id == session_id).all()
    )

    # Aggregate Books line items → one entry per (gstin, invoice_number)
    groups: Dict[tuple, List[BooksEntry]] = defaultdict(list)
    for b in raw_books:
        key = (b.gstin or "", b.invoice_number or "")
        groups[key].append(b)
    agg_books: List[_AggBooks] = [_AggBooks(v) for v in groups.values()]

    logger.info(
        "Session %d: %d raw books rows → %d unique invoices, %d GSTR-2B entries",
        session_id, len(raw_books), len(agg_books), len(gstr2b),
    )

    # Build inverted indexes for GSTR-2B
    val_indexes: List[Dict[str, List[GSTR2BEntry]]] = [defaultdict(list) for _ in range(5)]
    for g in gstr2b:
        for i, key in enumerate(_MATCH_KEYS):
            val = getattr(g, key) or ""
            if val:
                val_indexes[i][val].append(g)

    matched_gstr_ids: Set[int] = set()
    results: List[ReconciliationResult] = []
    summary: Dict[str, int] = {
        "total_books": len(raw_books),
        "total_gstr2b": len(gstr2b),
        "exact_match": 0,
        "strong_match": 0,
        "probable_match": 0,
        "manual_review": 0,
        "missing_in_books": 0,
    }

    for b in agg_books:
        candidate_scores: Dict[int, int] = defaultdict(int)
        candidate_map: Dict[int, GSTR2BEntry] = {}

        for i, key in enumerate(_MATCH_KEYS):
            bval = getattr(b, key) or ""
            if not bval:
                continue
            for g in val_indexes[i].get(bval, []):
                if g.id not in matched_gstr_ids:
                    candidate_scores[g.id] += 1
                    candidate_map[g.id] = g

        best_score = 0
        best_g: Optional[GSTR2BEntry] = None
        for gid, score in candidate_scores.items():
            if score > best_score:
                best_score = score
                best_g = candidate_map[gid]

        category = _category_for_score(best_score)
        reason   = _mismatch_reason(best_score, b, best_g)

        matched_gstr_id = None
        if best_g and best_score >= 2:
            matched_gstr_ids.add(best_g.id)
            matched_gstr_id = best_g.id

        results.append(ReconciliationResult(
            session_id=session_id,
            books_entry_id=b.id,
            gstr2b_entry_id=matched_gstr_id,
            match_score=best_score,
            match_category=category,
            mismatch_reason=reason,
            vendor_name=b.vendor_name,
            gstin=b.gstin,
            invoice_number=b.invoice_number,
            invoice_date=b.invoice_date,
            taxable_value=b.taxable_value,
            total_gst=b.total_gst,
            invoice_month=b.invoice_month,
            reconciliation_month=b.reconciliation_month,
            month_year=b.invoice_month,
        ))

        if category == _CAT_EXACT:        summary["exact_match"]    += 1
        elif category == _CAT_STRONG:     summary["strong_match"]   += 1
        elif category == _CAT_PROBABLE:   summary["probable_match"] += 1
        else:                             summary["manual_review"]  += 1

    # Unmatched GSTR-2B → Missing in Books
    for g in gstr2b:
        if g.id not in matched_gstr_ids:
            results.append(ReconciliationResult(
                session_id=session_id,
                books_entry_id=None,
                gstr2b_entry_id=g.id,
                match_score=0,
                match_category=_CAT_MISSING_BOOKS,
                mismatch_reason="Invoice present in GSTR-2B but not in Books",
                vendor_name=g.vendor_name,
                gstin=g.gstin,
                invoice_number=g.invoice_number,
                invoice_date=g.invoice_date,
                taxable_value=g.taxable_value,
                total_gst=g.total_gst,
                invoice_month=g.invoice_month,
                reconciliation_month=g.reconciliation_month,
                month_year=g.invoice_month,
            ))
            summary["missing_in_books"] += 1

    db.bulk_save_objects(results)

    session_obj = db.query(ReconciliationSession).filter(
        ReconciliationSession.id == session_id
    ).first()
    if session_obj:
        session_obj.status = "completed"

    db.add(AuditLog(
        session_id=session_id,
        action="reconciliation_complete",
        details=str(summary),
    ))
    db.commit()

    logger.info("Reconciliation complete for session %d: %s", session_id, summary)
    return summary
