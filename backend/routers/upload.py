import logging
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from database import get_db
from models import AuditLog, ReconciliationSession
from services.books_processor import process_books_file
from services.gstr2b_processor import process_gstr2b_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Upload"])

KNOWN_BRANCHES = ["AP", "BLR", "BBSR", "HYD", "MUM", "DEL", "CHN", "KOL", "PUN", "Other"]


@router.get("/branches")
def list_branches():
    return {"branches": KNOWN_BRANCHES}


@router.post("/upload/books")
async def upload_books(
    file: UploadFile = File(...),
    branch: str = Form(...),
    recon_month: str = Form(...),   # "YYYY-MM" e.g. "2024-03"
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only Excel files (.xlsx, .xls) are accepted.")

    recon_year = recon_month.split("-")[0] if "-" in recon_month else None

    session_obj = ReconciliationSession(
        status="processing",
        books_filename=file.filename,
        branch=branch.upper().strip(),
        recon_month=recon_month,
        recon_year=recon_year,
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)

    try:
        file_bytes = await file.read()
        books_count = process_books_file(file_bytes, session_obj.id, db,
                                         reconciliation_month=recon_month)
    except ValueError as exc:
        session_obj.status = "error"
        db.commit()
        raise HTTPException(422, str(exc))
    except Exception as exc:
        logger.exception("Error processing Books for session %d", session_obj.id)
        session_obj.status = "error"
        db.commit()
        raise HTTPException(500, f"Failed to process file: {exc}")

    session_obj.status = "books_uploaded"
    db.add(AuditLog(
        session_id=session_obj.id,
        action="books_uploaded",
        details=f"file={file.filename} branch={branch} recon_month={recon_month} records={books_count}",
    ))
    db.commit()
    return {
        "session_id": session_obj.id,
        "books_count": books_count,
        "branch": branch,
        "recon_month": recon_month,
        "filename": file.filename,
    }


@router.post("/upload/gstr2b/{session_id}")
async def upload_gstr2b(
    session_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    session_obj = db.query(ReconciliationSession).filter(
        ReconciliationSession.id == session_id
    ).first()
    if not session_obj:
        raise HTTPException(404, f"Session {session_id} not found.")
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only Excel files (.xlsx, .xls) are accepted.")

    try:
        file_bytes = await file.read()
        gstr2b_count = process_gstr2b_file(
            file_bytes, session_id, db,
            reconciliation_month=session_obj.recon_month or "",
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:
        logger.exception("Error processing GSTR-2B for session %d", session_id)
        raise HTTPException(500, f"Failed to process file: {exc}")

    session_obj.gstr2b_filename = file.filename
    session_obj.status = "ready_to_reconcile"
    db.add(AuditLog(
        session_id=session_id,
        action="gstr2b_uploaded",
        details=f"file={file.filename} records={gstr2b_count}",
    ))
    db.commit()
    return {
        "session_id": session_id,
        "gstr2b_count": gstr2b_count,
        "status": session_obj.status,
        "filename": file.filename,
    }


@router.get("/sessions")
def list_sessions(branch: str = None, recon_month: str = None, db: Session = Depends(get_db)):
    q = db.query(ReconciliationSession).order_by(ReconciliationSession.created_at.desc())
    if branch:
        q = q.filter(ReconciliationSession.branch == branch.upper())
    if recon_month:
        q = q.filter(ReconciliationSession.recon_month == recon_month)
    return [_session_dict(s) for s in q.limit(50).all()]


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    s = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
    if not s:
        raise HTTPException(404, f"Session {session_id} not found.")
    return _session_dict(s)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    s = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
    if not s:
        raise HTTPException(404, f"Session {session_id} not found.")
    db.delete(s)
    db.commit()
    return {"deleted": session_id}


def _session_dict(s: ReconciliationSession) -> dict:
    return {
        "id": s.id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "status": s.status,
        "books_filename": s.books_filename,
        "gstr2b_filename": s.gstr2b_filename,
        "branch": s.branch,
        "recon_month": s.recon_month,
        "recon_year": s.recon_year,
    }
