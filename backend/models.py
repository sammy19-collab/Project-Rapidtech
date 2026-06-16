from datetime import datetime, date as date_type
from sqlalchemy import (
    Column, DateTime, Date, ForeignKey, Integer,
    String, Text, Numeric, Index
)
from sqlalchemy.orm import relationship
from database import Base


class ReconciliationSession(Base):
    __tablename__ = "reconciliation_sessions"

    id              = Column(Integer, primary_key=True, index=True)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)
    status          = Column(String(50), nullable=False, default="processing")
    books_filename  = Column(String(255), nullable=True)
    gstr2b_filename = Column(String(255), nullable=True)
    branch          = Column(String(50), nullable=True, index=True)
    recon_month     = Column(String(7), nullable=True, index=True)  # YYYY-MM
    recon_year      = Column(String(4), nullable=True)

    books_entries = relationship("BooksEntry",          back_populates="session", cascade="all, delete-orphan")
    gstr2b_entries = relationship("GSTR2BEntry",        back_populates="session", cascade="all, delete-orphan")
    results        = relationship("ReconciliationResult", back_populates="session", cascade="all, delete-orphan")
    audit_logs     = relationship("AuditLog",            back_populates="session", cascade="all, delete-orphan")


class BooksEntry(Base):
    __tablename__ = "books_entries"

    id             = Column(Integer, primary_key=True, index=True)
    session_id     = Column(Integer, ForeignKey("reconciliation_sessions.id"), nullable=False, index=True)
    vendor_name    = Column(String(500), nullable=True)
    gstin          = Column(String(20),  nullable=True, index=True)
    invoice_number = Column(String(100), nullable=True, index=True)
    invoice_date   = Column(Date,        nullable=True)
    invoice_month  = Column(String(7),   nullable=True)   # MM-YYYY from invoice date
    reconciliation_month = Column(String(7), nullable=True)  # from upload selection
    taxable_value  = Column(Numeric(15, 2), nullable=True, default=0)
    cgst           = Column(Numeric(15, 2), nullable=True, default=0)
    sgst           = Column(Numeric(15, 2), nullable=True, default=0)
    igst           = Column(Numeric(15, 2), nullable=True, default=0)
    total_gst      = Column(Numeric(15, 2), nullable=True, default=0)
    expense_type   = Column(String(200), nullable=True)
    narration      = Column(Text,        nullable=True)
    val1 = Column(String(500), nullable=True, index=True)
    val2 = Column(String(500), nullable=True, index=True)
    val3 = Column(String(500), nullable=True, index=True)
    val4 = Column(String(500), nullable=True, index=True)
    val5 = Column(String(500), nullable=True, index=True)

    session = relationship("ReconciliationSession", back_populates="books_entries")


class GSTR2BEntry(Base):
    __tablename__ = "gstr2b_entries"

    id             = Column(Integer, primary_key=True, index=True)
    session_id     = Column(Integer, ForeignKey("reconciliation_sessions.id"), nullable=False, index=True)
    vendor_name    = Column(String(500), nullable=True)
    gstin          = Column(String(20),  nullable=True, index=True)
    invoice_number = Column(String(100), nullable=True, index=True)
    invoice_date   = Column(Date,        nullable=True)
    invoice_month  = Column(String(7),   nullable=True)   # MM-YYYY from invoice date
    filing_month   = Column(String(7),   nullable=True)   # MM-YYYY from GSTR-2B period
    reconciliation_month = Column(String(7), nullable=True)
    taxable_value  = Column(Numeric(15, 2), nullable=True, default=0)
    cgst           = Column(Numeric(15, 2), nullable=True, default=0)
    sgst           = Column(Numeric(15, 2), nullable=True, default=0)
    igst           = Column(Numeric(15, 2), nullable=True, default=0)
    total_gst      = Column(Numeric(15, 2), nullable=True, default=0)
    val1 = Column(String(500), nullable=True, index=True)
    val2 = Column(String(500), nullable=True, index=True)
    val3 = Column(String(500), nullable=True, index=True)
    val4 = Column(String(500), nullable=True, index=True)
    val5 = Column(String(500), nullable=True, index=True)

    session = relationship("ReconciliationSession", back_populates="gstr2b_entries")


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    id              = Column(Integer, primary_key=True, index=True)
    session_id      = Column(Integer, ForeignKey("reconciliation_sessions.id"), nullable=False, index=True)
    books_entry_id  = Column(Integer, ForeignKey("books_entries.id"),  nullable=True)
    gstr2b_entry_id = Column(Integer, ForeignKey("gstr2b_entries.id"), nullable=True)
    match_score     = Column(Integer, nullable=False, default=0)
    match_category  = Column(String(50), nullable=False)
    mismatch_reason = Column(Text, nullable=True)
    vendor_name     = Column(String(500), nullable=True)
    gstin           = Column(String(20),  nullable=True)
    invoice_number  = Column(String(100), nullable=True)
    invoice_date    = Column(Date,        nullable=True)
    taxable_value   = Column(Numeric(15, 2), nullable=True, default=0)
    total_gst       = Column(Numeric(15, 2), nullable=True, default=0)
    invoice_month        = Column(String(7), nullable=True, index=True)   # MM-YYYY
    reconciliation_month = Column(String(7), nullable=True, index=True)
    month_year           = Column(String(7), nullable=True, index=True)   # same as invoice_month, kept for UI compat

    session      = relationship("ReconciliationSession", back_populates="results")
    books_entry  = relationship("BooksEntry",  foreign_keys=[books_entry_id])
    gstr2b_entry = relationship("GSTR2BEntry", foreign_keys=[gstr2b_entry_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id         = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("reconciliation_sessions.id"), nullable=True, index=True)
    action     = Column(String(100), nullable=False)
    timestamp  = Column(DateTime, default=datetime.utcnow, nullable=False)
    details    = Column(Text, nullable=True)

    session = relationship("ReconciliationSession", back_populates="audit_logs")
