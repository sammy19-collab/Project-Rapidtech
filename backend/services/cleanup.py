"""
Periodic cleanup: delete reconciliation sessions older than 30 days.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from database import SessionLocal
from models import ReconciliationSession

logger = logging.getLogger(__name__)


def cleanup_old_sessions(days: int = 30) -> int:
    """Delete sessions created more than `days` days ago. Returns count deleted."""
    db: Session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = (
            db.query(ReconciliationSession)
            .filter(ReconciliationSession.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted:
            logger.info("Cleanup: deleted %d sessions older than %d days", deleted, days)
        return deleted
    except Exception as exc:
        db.rollback()
        logger.error("Cleanup error: %s", exc)
        return 0
    finally:
        db.close()
