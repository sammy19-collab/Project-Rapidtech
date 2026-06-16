"""
RapidTech GST Reconciliation API - FastAPI application entry point.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routers import upload, reconciliation, tally, dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RapidTech GST Reconciliation API",
    description=(
        "Backend API for GST Input Tax Credit Reconciliation and "
        "automated Tally XML generation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(reconciliation.router)
app.include_router(tally.router)
app.include_router(dashboard.router)


@app.on_event("startup")
async def startup_event():
    """Create DB tables (retry until DB is ready) and start background cleanup scheduler."""
    import time
    from sqlalchemy import text

    for attempt in range(1, 11):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except Exception as exc:
            logger.warning("DB not ready (attempt %d/10): %s", attempt, exc)
            time.sleep(3)

    logger.info("Creating database tables if they do not exist...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")

    # Daily cleanup of sessions older than 30 days
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from services.cleanup import cleanup_old_sessions

        scheduler = BackgroundScheduler()
        scheduler.add_job(cleanup_old_sessions, "interval", hours=24, id="cleanup")
        scheduler.start()
        logger.info("APScheduler started: daily session cleanup enabled.")
    except ImportError:
        logger.warning("apscheduler not installed — session auto-cleanup disabled.")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "RapidTech GST Reconciliation API"}
