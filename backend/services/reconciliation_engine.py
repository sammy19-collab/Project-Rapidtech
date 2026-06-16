"""
Core reconciliation engine: matches BooksEntry rows against GSTR2BEntry rows
using five composite validation keys and assigns match categories.
"""

import logging
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from models import BooksEntry, GSTR2BEntry, ReconciliationResult, ReconciliationSession

logger = logging.getLogger(__name__)

_MATCH_KEYS = ["val1", "val2", "val3", "val4", "val5"]

# Category thresholds
_CAT_EXACT = "Exact Match"
_CAT_STRONG = "Strong Match"
_CAT_PROBABLE = "Probable Match"
_CAT_MANUAL = "Manual Review"
_CAT_MISSING_BOOKS = "Missing in Books"


def _score_pair(b: BooksEntry, g: GSTR2BEntry) -> int:
    """Count how many of val1..val5 match between a BooksEntry and a GSTR2BEntry."""
    score = 0
    for key in _MATCH_KEYS:
        bv = getattr(b, key) or ""
        gv = getattr(g, key) or ""
        if bv and gv and bv == gv:
            score += 1
    return score


def _category_for_score(score: int) -> str:
    if score == 5:
        return _CAT_EXACT
    if score == 4:
        return _CAT_STRONG
    if score in (2, 3):
        return _CAT_PROBABLE
    return _CAT_MANUAL


def _extract_month_year(date_str: str | None) -> str | None:
    """Convert 'DD-MM-YYYY' → 'MM-YYYY' for grouping."""
    if not date_str:
        return None
    parts = str(date_str).split("-")
    if len(parts) == 3 and len(parts[2]) == 4:
        return f"{parts[1]}-{parts[2]}"
    return None


def _mismatch_reason(score: int, b: BooksEntry, g: Optional[GSTR2BEntry]) -> Optional[str]:
    """Generate a human-readable mismatch reason for non-exact matches."""
    if score == 5:
        return None
    if g is None:
        return "No matching invoice found in GSTR-2B"
    reasons = []
    if (b.gstin or "") != (g.gstin or ""):
        reasons.append("GSTIN mismatch")
    if (b.invoice_number or "") != (g.invoice_number or ""):
        reasons.append("Invoice number mismatch")
    if (b.invoice_date or "") != (g.invoice_date or ""):
        reasons.append("Invoice date mismatch")
    if abs((b.taxable_value or 0.0) - (g.taxable_value or 0.0)) > 1.0:
        reasons.append("Taxable value mismatch")
    return "; ".join(reasons) if reasons else "Partial key mismatch"


def run_reconciliation(session_id: int, db: Session) -> dict:
    """
    Match every BooksEntry against every GSTR2BEntry for the given session
    using the five composite validation keys.

    Algorithm:
        For each books entry find the GSTR2B entry with the highest key overlap.
        Score thresholds determine the match category.
        Unmatched GSTR2B entries are recorded as "Missing in Books".

    Returns:
        Summary dictionary with counts per category.
    """
    # Delete any previous results for this session (re-run support)
    db.query(ReconciliationResult).filter(
        ReconciliationResult.session_id == session_id
    ).delete()
    db.commit()

    books: List[BooksEntry] = (
        db.query(BooksEntry).filter(BooksEntry.session_id == session_id).all()
    )
    gstr2b: List[GSTR2BEntry] = (
        db.query(GSTR2BEntry).filter(GSTR2BEntry.session_id == session_id).all()
    )

    matched_gstr2b_ids: Set[int] = set()

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
        best_score = 0
        best_g: Optional[GSTR2BEntry] = None

        for g in gstr2b:
            score = _score_pair(b, g)
            if score > best_score:
                best_score = score
                best_g = g

        category = _category_for_score(best_score)
        reason = _mismatch_reason(best_score, b, best_g)

        if best_g and best_score >= 2:
            matched_gstr2b_ids.add(best_g.id)

        result = ReconciliationResult(
            session_id=session_id,
            books_entry_id=b.id,
            gstr2b_entry_id=best_g.id if best_g and best_score >= 2 else None,
            match_score=best_score,
            match_category=category,
            mismatch_reason=reason,
            vendor_name=b.vendor_name,
            gstin=b.gstin,
            invoice_number=b.invoice_number,
            invoice_date=b.invoice_date,
            taxable_value=b.taxable_value,
            total_gst=b.total_gst,
            month_year=_extract_month_year(b.invoice_date),
        )
        results.append(result)

        # Tally summary
        if category == _CAT_EXACT:
            summary["exact_match"] += 1
        elif category == _CAT_STRONG:
            summary["strong_match"] += 1
        elif category == _CAT_PROBABLE:
            summary["probable_match"] += 1
        else:
            summary["manual_review"] += 1

    # Unmatched GSTR2B -> Missing in Books
    for g in gstr2b:
        if g.id not in matched_gstr2b_ids:
            total_gst = round((g.cgst or 0) + (g.sgst or 0) + (g.igst or 0), 2)
            result = ReconciliationResult(
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
                total_gst=total_gst,
                month_year=_extract_month_year(g.invoice_date),
            )
            results.append(result)
            summary["missing_in_books"] += 1

    db.bulk_save_objects(results)

    # Update session status
    session_obj = db.query(ReconciliationSession).filter(
        ReconciliationSession.id == session_id
    ).first()
    if session_obj:
        session_obj.status = "completed"
    db.commit()

    logger.info("Reconciliation complete for session %d: %s", session_id, summary)
    return summary
