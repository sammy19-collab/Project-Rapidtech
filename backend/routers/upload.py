"""
Upload router: handles Books and GSTR-2B file uploads and session management.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from models import ReconciliationSession
from services.books_processor import process_books_file
from services.gstr2b_processor import process_gstr2b_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Upload"])


@router.post("/upload/books")
async def upload_books(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload the company purchase books Excel file (.xlsx).

    Creates a new ReconciliationSession and processes the 'Books' sheet.
    Returns the new session ID and number of records loaded.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Excel files (.xlsx, .xls) are accepted.",
        )

    session_obj = ReconciliationSession(
        status="processing",
        books_filename=file.filename,
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    session_id = session_obj.id

    try:
        file_bytes = await file.read()
        books_count = process_books_file(file_bytes, session_id, db)
    except ValueError as exc:
        session_obj.status = "error"
        db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error processing Books file for session %d", session_id)
        session_obj.status = "error"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {exc}",
        )

    session_obj.status = "books_uploaded"
    db.commit()

    return {
        "session_id": session_id,
        "books_count": books_count,
        "status": session_obj.status,
    }


@router.post("/upload/gstr2b/{session_id}")
async def upload_gstr2b(
    session_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload the GSTR-2B Excel export for an existing session.

    Processes the '2B' sheet and marks the session as ready to reconcile.
    """
    session_obj = db.query(ReconciliationSession).filter(
        ReconciliationSession.id == session_id
    ).first()
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found.",
        )

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Excel files (.xlsx, .xls) are accepted.",
        )

    try:
        file_bytes = await file.read()
        gstr2b_count = process_gstr2b_file(file_bytes, session_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error processing GSTR-2B file for session %d", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {exc}",
        )

    session_obj.gstr2b_filename = file.filename
    session_obj.status = "ready_to_reconcile"
    db.commit()

    return {
        "session_id": session_id,
        "gstr2b_count": gstr2b_count,
        "status": session_obj.status,
    }


@router.get("/sessions")
async def list_sessions(db: Session = Depends(get_db)):
    """Return a list of all reconciliation sessions, newest first."""
    sessions = (
        db.query(ReconciliationSession)
        .order_by(ReconciliationSession.created_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "status": s.status,
            "books_filename": s.books_filename,
            "gstr2b_filename": s.gstr2b_filename,
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: int, db: Session = Depends(get_db)):
    """Return details for a specific reconciliation session."""
    session_obj = db.query(ReconciliationSession).filter(
        ReconciliationSession.id == session_id
    ).first()
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found.",
        )
    return {
        "id": session_obj.id,
        "created_at": session_obj.created_at.isoformat() if session_obj.created_at else None,
        "status": session_obj.status,
        "books_filename": session_obj.books_filename,
        "gstr2b_filename": session_obj.gstr2b_filename,
    }
