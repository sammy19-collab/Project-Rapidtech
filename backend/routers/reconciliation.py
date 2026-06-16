"""
Reconciliation router: triggers matching and exposes result endpoints.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import ReconciliationResult, ReconciliationSession
from services.reconciliation_engine import run_reconciliation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Reconciliation"])


def _result_to_dict(r: ReconciliationResult) -> dict:
    return {
        "id": r.id,
        "session_id": r.session_id,
        "books_entry_id": r.books_entry_id,
        "gstr2b_entry_id": r.gstr2b_entry_id,
        "match_score": r.match_score,
        "match_category": r.match_category,
        "mismatch_reason": r.mismatch_reason,
        "vendor_name": r.vendor_name,
        "gstin": r.gstin,
        "invoice_number": r.invoice_number,
        "invoice_date": r.invoice_date,
        "taxable_value": r.taxable_value,
        "total_gst": r.total_gst,
    }


def _get_session_or_404(session_id: int, db: Session) -> ReconciliationSession:
    obj = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found.",
        )
    return obj


@router.post("/reconcile/{session_id}")
async def reconcile(session_id: int, db: Session = Depends(get_db)):
    """
    Trigger the reconciliation process for a session.

    Requires both Books and GSTR-2B files to have been uploaded.
    Returns a summary of match categories.
    """
    session_obj = _get_session_or_404(session_id, db)
    if session_obj.status not in ("ready_to_reconcile", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is in status '{session_obj.status}'. "
                   "Both files must be uploaded before reconciling.",
        )

    try:
        summary = run_reconciliation(session_id, db)
    except Exception as exc:
        logger.exception("Reconciliation failed for session %d", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation failed: {exc}",
        )
    return {"session_id": session_id, "summary": summary}


@router.get("/results/{session_id}")
async def get_results(
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return all reconciliation results for a session (paginated)."""
    _get_session_or_404(session_id, db)
    results = (
        db.query(ReconciliationResult)
        .filter(ReconciliationResult.session_id == session_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = (
        db.query(ReconciliationResult)
        .filter(ReconciliationResult.session_id == session_id)
        .count()
    )
    return {"total": total, "skip": skip, "limit": limit, "data": [_result_to_dict(r) for r in results]}


@router.get("/results/{session_id}/reconciled")
async def get_reconciled(
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return Exact Match + Strong Match results."""
    _get_session_or_404(session_id, db)
    q = db.query(ReconciliationResult).filter(
        ReconciliationResult.session_id == session_id,
        ReconciliationResult.match_category.in_(["Exact Match", "Strong Match"]),
    )
    total = q.count()
    results = q.offset(skip).limit(limit).all()
    return {"total": total, "data": [_result_to_dict(r) for r in results]}


@router.get("/results/{session_id}/probable")
async def get_probable(
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return Probable Match results."""
    _get_session_or_404(session_id, db)
    q = db.query(ReconciliationResult).filter(
        ReconciliationResult.session_id == session_id,
        ReconciliationResult.match_category == "Probable Match",
    )
    total = q.count()
    results = q.offset(skip).limit(limit).all()
    return {"total": total, "data": [_result_to_dict(r) for r in results]}


@router.get("/results/{session_id}/missing-in-books")
async def get_missing_in_books(
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return invoices present in GSTR-2B but missing in Books."""
    _get_session_or_404(session_id, db)
    q = db.query(ReconciliationResult).filter(
        ReconciliationResult.session_id == session_id,
        ReconciliationResult.match_category == "Missing in Books",
    )
    total = q.count()
    results = q.offset(skip).limit(limit).all()
    return {"total": total, "data": [_result_to_dict(r) for r in results]}


@router.get("/results/{session_id}/missing-in-gstr2b")
async def get_missing_in_gstr2b(
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return Books entries with no match in GSTR-2B (Manual Review)."""
    _get_session_or_404(session_id, db)
    q = db.query(ReconciliationResult).filter(
        ReconciliationResult.session_id == session_id,
        ReconciliationResult.match_category == "Manual Review",
    )
    total = q.count()
    results = q.offset(skip).limit(limit).all()
    return {"total": total, "data": [_result_to_dict(r) for r in results]}
