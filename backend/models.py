"""
SQLAlchemy ORM models for RapidTech GST Reconciliation App.
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


class ReconciliationSession(Base):
    """Tracks a single reconciliation job (one Books upload + one GSTR-2B upload)."""

    __tablename__ = "reconciliation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(50), nullable=False, default="processing")
    books_filename = Column(String(255), nullable=True)
    gstr2b_filename = Column(String(255), nullable=True)

    books_entries = relationship(
        "BooksEntry", back_populates="session", cascade="all, delete-orphan"
    )
    gstr2b_entries = relationship(
        "GSTR2BEntry", back_populates="session", cascade="all, delete-orphan"
    )
    results = relationship(
        "ReconciliationResult", back_populates="session", cascade="all, delete-orphan"
    )


class BooksEntry(Base):
    """Represents one invoice row from the company's purchase books (Excel upload)."""

    __tablename__ = "books_entries"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("reconciliation_sessions.id"), nullable=False, index=True
    )

    # Vendor / invoice fields
    vendor_name = Column(String(500), nullable=True)
    gstin = Column(String(20), nullable=True)
    invoice_number = Column(String(100), nullable=True)
    invoice_date = Column(String(50), nullable=True)
    taxable_value = Column(Float, nullable=True, default=0.0)
    cgst = Column(Float, nullable=True, default=0.0)
    sgst = Column(Float, nullable=True, default=0.0)
    igst = Column(Float, nullable=True, default=0.0)
    total_gst = Column(Float, nullable=True, default=0.0)
    expense_type = Column(String(200), nullable=True)
    narration = Column(Text, nullable=True)

    # Composite validation keys for fuzzy matching
    val1 = Column(String(500), nullable=True, index=True)
    val2 = Column(String(500), nullable=True, index=True)
    val3 = Column(String(500), nullable=True, index=True)
    val4 = Column(String(500), nullable=True, index=True)
    val5 = Column(String(500), nullable=True, index=True)

    session = relationship("ReconciliationSession", back_populates="books_entries")


class GSTR2BEntry(Base):
    """Represents one invoice row from the GSTR-2B portal export."""

    __tablename__ = "gstr2b_entries"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("reconciliation_sessions.id"), nullable=False, index=True
    )

    vendor_name = Column(String(500), nullable=True)
    gstin = Column(String(20), nullable=True)
    invoice_number = Column(String(100), nullable=True)
    invoice_date = Column(String(50), nullable=True)
    taxable_value = Column(Float, nullable=True, default=0.0)
    cgst = Column(Float, nullable=True, default=0.0)
    sgst = Column(Float, nullable=True, default=0.0)
    igst = Column(Float, nullable=True, default=0.0)

    # Composite validation keys
    val1 = Column(String(500), nullable=True, index=True)
    val2 = Column(String(500), nullable=True, index=True)
    val3 = Column(String(500), nullable=True, index=True)
    val4 = Column(String(500), nullable=True, index=True)
    val5 = Column(String(500), nullable=True, index=True)

    session = relationship("ReconciliationSession", back_populates="gstr2b_entries")


class ReconciliationResult(Base):
    """Stores the outcome of matching a BooksEntry against GSTR-2B entries."""

    __tablename__ = "reconciliation_results"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("reconciliation_sessions.id"), nullable=False, index=True
    )
    books_entry_id = Column(
        Integer, ForeignKey("books_entries.id"), nullable=True
    )
    gstr2b_entry_id = Column(
        Integer, ForeignKey("gstr2b_entries.id"), nullable=True
    )

    match_score = Column(Integer, nullable=False, default=0)
    match_category = Column(String(50), nullable=False)
    mismatch_reason = Column(Text, nullable=True)

    # Denormalized display fields (populated from whichever side exists)
    vendor_name = Column(String(500), nullable=True)
    gstin = Column(String(20), nullable=True)
    invoice_number = Column(String(100), nullable=True)
    invoice_date = Column(String(50), nullable=True)
    taxable_value = Column(Float, nullable=True, default=0.0)
    total_gst = Column(Float, nullable=True, default=0.0)

    session = relationship("ReconciliationSession", back_populates="results")
    books_entry = relationship("BooksEntry", foreign_keys=[books_entry_id])
    gstr2b_entry = relationship("GSTR2BEntry", foreign_keys=[gstr2b_entry_id])
