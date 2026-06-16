from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from models import AuditLog, ReconciliationSession, ReconciliationResult
from services.reconciliation_engine import run_reconciliation

router = APIRouter(prefix="/api", tags=["Reconciliation"])


def _fmt(v) -> str | None:
    """Serialize date/Decimal to JSON-safe types."""
    if v is None:
        return None
    return str(v)


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
        "invoice_date": _fmt(r.invoice_date),
        "taxable_value": _fmt(r.taxable_value),
        "total_gst": _fmt(r.total_gst),
        "invoice_month": r.invoice_month,
        "reconciliation_month": r.reconciliation_month,
        "month_year": r.month_year,
    }


def _base_query(session_id: int, month_year: str | None, db: Session):
    q = db.query(ReconciliationResult).filter(ReconciliationResult.session_id == session_id)
    if month_year:
        q = q.filter(ReconciliationResult.month_year == month_year)
    return q


@router.post("/reconcile/{session_id}")
def reconcile(session_id: int, db: Session = Depends(get_db)):
    session_obj = db.query(ReconciliationSession).filter(
        ReconciliationSession.id == session_id
    ).first()
    if not session_obj:
        raise HTTPException(404, "Session not found")
    summary = run_reconciliation(session_id, db)
    return {"session_id": session_id, "summary": summary}


@router.get("/results/{session_id}/months")
def get_available_months(session_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(ReconciliationResult.month_year)
        .filter(
            ReconciliationResult.session_id == session_id,
            ReconciliationResult.month_year.isnot(None),
        )
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


@router.get("/audit/{session_id}")
def get_audit_log(session_id: int, db: Session = Depends(get_db)):
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.session_id == session_id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    return [
        {
            "id": l.id,
            "action": l.action,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "details": l.details,
        }
        for l in logs
    ]
