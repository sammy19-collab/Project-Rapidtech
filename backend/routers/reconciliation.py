from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from models import ReconciliationSession, ReconciliationResult
from services.reconciliation_engine import run_reconciliation

router = APIRouter(prefix="/api", tags=["Reconciliation"])


def _result_dict(r: ReconciliationResult) -> dict:
    return {
        "id": r.id,
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
        "month_year": r.month_year,
    }


def _base_query(session_id: int, month_year: str | None, db: Session):
    q = db.query(ReconciliationResult).filter(ReconciliationResult.session_id == session_id)
    if month_year:
        q = q.filter(ReconciliationResult.month_year == month_year)
    return q


@router.post("/reconcile/{session_id}")
def reconcile(session_id: int, db: Session = Depends(get_db)):
    session_obj = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
    if not session_obj:
        raise HTTPException(404, "Session not found")
    summary = run_reconciliation(session_id, db)
    return {"session_id": session_id, "summary": summary}


@router.get("/results/{session_id}/months")
def get_available_months(session_id: int, db: Session = Depends(get_db)):
    """Return distinct month_year values present in results for this session."""
    rows = (
        db.query(ReconciliationResult.month_year)
        .filter(ReconciliationResult.session_id == session_id, ReconciliationResult.month_year != None)
        .distinct()
        .order_by(ReconciliationResult.month_year)
        .all()
    )
    return {"months": [r[0] for r in rows]}


@router.get("/results/{session_id}")
def get_all_results(session_id: int, month_year: str = Query(None), db: Session = Depends(get_db)):
    return [_result_dict(r) for r in _base_query(session_id, month_year, db).all()]


@router.get("/results/{session_id}/reconciled")
def get_reconciled(session_id: int, month_year: str = Query(None), db: Session = Depends(get_db)):
    q = _base_query(session_id, month_year, db).filter(
        ReconciliationResult.match_category.in_(["Exact Match", "Strong Match"])
    )
    return [_result_dict(r) for r in q.all()]


@router.get("/results/{session_id}/probable")
def get_probable(session_id: int, month_year: str = Query(None), db: Session = Depends(get_db)):
    q = _base_query(session_id, month_year, db).filter(
        ReconciliationResult.match_category == "Probable Match"
    )
    return [_result_dict(r) for r in q.all()]


@router.get("/results/{session_id}/missing-in-books")
def get_missing_in_books(session_id: int, month_year: str = Query(None), db: Session = Depends(get_db)):
    q = _base_query(session_id, month_year, db).filter(
        ReconciliationResult.match_category == "Missing in Books"
    )
    return [_result_dict(r) for r in q.all()]


@router.get("/results/{session_id}/missing-in-gstr2b")
def get_missing_in_gstr2b(session_id: int, month_year: str = Query(None), db: Session = Depends(get_db)):
    q = _base_query(session_id, month_year, db).filter(
        ReconciliationResult.match_category == "Manual Review"
    )
    return [_result_dict(r) for r in q.all()]
