"""
Core reconciliation engine: O(n) hash-based matching of BooksEntry against
GSTR2BEntry rows using five composite validation keys.
"""

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from models import AuditLog, BooksEntry, GSTR2BEntry, ReconciliationResult, ReconciliationSession

logger = logging.getLogger(__name__)

_MATCH_KEYS = ["val1", "val2", "val3", "val4", "val5"]

_CAT_EXACT        = "Exact Match"
_CAT_STRONG       = "Strong Match"
_CAT_PROBABLE     = "Probable Match"
_CAT_MANUAL       = "Manual Review"
_CAT_MISSING_BOOKS = "Missing in Books"


def _category_for_score(score: int) -> str:
    if score == 5: return _CAT_EXACT
    if score == 4: return _CAT_STRONG
    if score in (2, 3): return _CAT_PROBABLE
    return _CAT_MANUAL


def _month_year_from_date(d) -> Optional[str]:
    """Return MM-YYYY from a date object or string."""
    if d is None:
        return None
    if isinstance(d, date):
        return d.strftime("%m-%Y")
    parts = str(d).split("-")
    if len(parts) == 3 and len(parts[2]) == 4:
        return f"{parts[1]}-{parts[2]}"
    return None


def _mismatch_reason(score: int, b: BooksEntry, g: Optional[GSTR2BEntry]) -> Optional[str]:
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
    b_tv = b.taxable_value or Decimal("0")
    g_tv = g.taxable_value or Decimal("0")
    if abs(b_tv - g_tv) > Decimal("1.00"):
        reasons.append("Taxable value mismatch")
    return "; ".join(reasons) if reasons else "Partial key mismatch"


def run_reconciliation(session_id: int, db: Session) -> dict:
    """
    O(n) hash-based reconciliation. For each books entry, look up candidates
    from val1→val5 indexes (highest key = best match). One-to-one: each GSTR-2B
    entry can only be matched once.
    """
    # Delete prior results for re-run support
    db.query(ReconciliationResult).filter(
        ReconciliationResult.session_id == session_id
    ).delete(synchronize_session=False)
    db.flush()

    books: List[BooksEntry] = (
        db.query(BooksEntry).filter(BooksEntry.session_id == session_id).all()
    )
    gstr2b: List[GSTR2BEntry] = (
        db.query(GSTR2BEntry).filter(GSTR2BEntry.session_id == session_id).all()
    )

    # Build inverted indexes: {key_value -> [GSTR2BEntry, ...]} for each val slot
    val_indexes: List[Dict[str, List[GSTR2BEntry]]] = [defaultdict(list) for _ in range(5)]
    for g in gstr2b:
        for i, key in enumerate(_MATCH_KEYS):
            val = getattr(g, key) or ""
            if val:
                val_indexes[i][val].append(g)

    matched_gstr_ids: Set[int] = set()

    summary: Dict[str, int] = {
        "total_books": len(books),
        "total_gstr2b": len(gstr2b),
        "exact_match": 0,
        "strong_match": 0,
        "probable_match": 0,
        "manual_review": 0,
        "missing_in_books": 0,
    }

    results: List[ReconciliationResult] = []

    for b in books:
        # Collect candidate scores: {gstr_id -> score}
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
