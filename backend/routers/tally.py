"""
Tally router: generate and download Tally XML import files.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from database import get_db
from models import ReconciliationResult, ReconciliationSession
from services.tally_generator import generate_tally_xml
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tally", tags=["Tally"])


def _check_session(session_id: int, db: Session) -> ReconciliationSession:
    obj = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found.",
        )
    if obj.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reconciliation must be completed before generating Tally XML.",
        )
    return obj


@router.get("/{session_id}/xml")
async def download_tally_xml(session_id: int, db: Session = Depends(get_db)):
    """
    Generate and return a Tally-compatible XML file for all reconciled invoices
    (Exact Match + Strong Match) as a downloadable attachment.
    """
    _check_session(session_id, db)

    try:
        xml_content = generate_tally_xml(session_id, db)
    except Exception as exc:
        logger.exception("Tally XML generation failed for session %d", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Tally XML: {exc}",
        )

    filename = f"tally_import_session_{session_id}.xml"
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/preview")
async def preview_tally_xml(session_id: int, db: Session = Depends(get_db)):
    """
    Return a preview of the Tally XML limited to the first 5 vouchers.
    Response is returned as JSON containing the XML string.
    """
    _check_session(session_id, db)

    try:
        xml_content = generate_tally_xml(session_id, db, limit=5)
    except Exception as exc:
        logger.exception("Tally XML preview failed for session %d", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Tally XML preview: {exc}",
        )

    total_reconciled = (
        db.query(ReconciliationResult)
        .filter(
            ReconciliationResult.session_id == session_id,
            ReconciliationResult.match_category.in_(["Exact Match", "Strong Match"]),
        )
        .count()
    )

    return {
        "session_id": session_id,
        "preview_vouchers": 5,
        "total_reconciled": total_reconciled,
        "xml_preview": xml_content,
    }
