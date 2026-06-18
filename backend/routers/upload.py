import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import AuditLog, ReconciliationSession, GSTR2BUpload, BooksEntry, GSTR2BEntry, ReconciliationResult
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
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only Excel files (.xlsx, .xls) are accepted.")

    session_obj = ReconciliationSession(status="processing", books_filename=file.filename)
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)

    try:
        file_bytes = await file.read()
        books_count, detected_branch = process_books_file(
            file_bytes, session_obj.id, db, filename=file.filename,
        )
    except ValueError as exc:
        session_obj.status = "error"
        db.commit()
        raise HTTPException(422, str(exc))
    except Exception as exc:
        logger.exception("Error processing Books for session %d", session_obj.id)
        session_obj.status = "error"
        db.commit()
        raise HTTPException(500, f"Failed to process file: {exc}")

    session_obj.branch = detected_branch
    session_obj.status = "books_uploaded"
    db.add(AuditLog(
        session_id=session_obj.id,
        action="books_uploaded",
        details=f"file={file.filename} branch={detected_branch} records={books_count}",
    ))
    db.commit()
    return {
        "session_id": session_obj.id,
        "books_count": books_count,
        "branch": branch,
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
        gstr2b_count, detected_month, detected_branch = process_gstr2b_file(
            file_bytes, session_id, db,
            filename=file.filename,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:
        logger.exception("Error processing GSTR-2B for session %d", session_id)
        raise HTTPException(500, f"Failed to process file: {exc}")

    db.add(GSTR2BUpload(session_id=session_id, filename=file.filename, record_count=gstr2b_count))

    # Update session period and branch from first GSTR-2B file
    if detected_month and not session_obj.recon_month:
        session_obj.recon_month = detected_month
        session_obj.recon_year = detected_month.split("-")[0]
    if detected_branch and detected_branch != "Other" and not session_obj.branch:
        session_obj.branch = detected_branch

    session_obj.gstr2b_filename = file.filename
    session_obj.status = "ready_to_reconcile"
    db.add(AuditLog(
        session_id=session_id,
        action="gstr2b_uploaded",
        details=f"file={file.filename} branch={detected_branch} month={detected_month} records={gstr2b_count}",
    ))
    db.commit()
    return {
        "session_id": session_id,
        "gstr2b_count": gstr2b_count,
        "detected_month": detected_month,
        "detected_branch": detected_branch,
        "status": session_obj.status,
        "filename": file.filename,
    }


@router.get("/sessions/{session_id}/gstr2b-files")
def list_gstr2b_files(session_id: int, db: Session = Depends(get_db)):
    session_obj = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
    if not session_obj:
        raise HTTPException(404, f"Session {session_id} not found.")
    uploads = db.query(GSTR2BUpload).filter(GSTR2BUpload.session_id == session_id).order_by(GSTR2BUpload.uploaded_at).all()
    total = sum(u.record_count for u in uploads)
    return {
        "session_id": session_id,
        "files": [
            {
                "id": u.id,
                "filename": u.filename,
                "record_count": u.record_count,
                "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else None,
            }
            for u in uploads
        ],
        "total_records": total,
    }


@router.get("/sessions")
def list_sessions(branch: str = None, recon_month: str = None, db: Session = Depends(get_db)):
    q = db.query(ReconciliationSession).order_by(ReconciliationSession.created_at.desc())
    if branch:
        q = q.filter(ReconciliationSession.branch == branch.upper())
    if recon_month:
        q = q.filter(ReconciliationSession.recon_month == recon_month)
    return [_session_dict(s, db) for s in q.limit(50).all()]


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    s = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
    if not s:
        raise HTTPException(404, f"Session {session_id} not found.")
    return _session_dict(s, db)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    s = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
    if not s:
        raise HTTPException(404, f"Session {session_id} not found.")
    db.delete(s)
    db.commit()
    return {"deleted": session_id}


def _session_dict(s: ReconciliationSession, db: Session) -> dict:
    books_count = db.query(func.count(BooksEntry.id)).filter(BooksEntry.session_id == s.id).scalar() or 0
    gstr2b_count = db.query(func.count(GSTR2BEntry.id)).filter(GSTR2BEntry.session_id == s.id).scalar() or 0

    result_counts = {
        "exact": 0, "strong": 0, "probable": 0, "manual": 0, "missing_books": 0
    }
    rows = (
        db.query(ReconciliationResult.match_category, func.count(ReconciliationResult.id))
        .filter(ReconciliationResult.session_id == s.id)
        .group_by(ReconciliationResult.match_category)
        .all()
    )
    cat_map = {
        "Exact Match": "exact",
        "Strong Match": "strong",
        "Probable Match": "probable",
        "Manual Review": "manual",
        "Missing in Books": "missing_books",
    }
    for category, cnt in rows:
        key = cat_map.get(category)
        if key:
            result_counts[key] = cnt

    return {
        "id": s.id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "status": s.status,
        "books_filename": s.books_filename,
        "gstr2b_filename": s.gstr2b_filename,
        "branch": s.branch,
        "recon_month": s.recon_month,
        "recon_year": s.recon_year,
        "books_count": books_count,
        "gstr2b_count": gstr2b_count,
        "result_counts": result_counts,
    }
