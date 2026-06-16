"""
Dashboard router: aggregated analytics for a reconciliation session.
"""

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import ReconciliationResult, ReconciliationSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

_RECONCILED = {"Exact Match", "Strong Match"}
_MISMATCHED = {"Manual Review", "Missing in Books"}


@router.get("/{session_id}")
async def get_dashboard(session_id: int, db: Session = Depends(get_db)):
    """
    Return aggregated dashboard metrics for a reconciliation session.

    Includes:
        - Counts per category
        - Reconciliation percentage
        - Total and at-risk ITC amounts
        - Top vendors by ITC amount
        - Monthly trend (reconciled vs mismatched)
        - Mismatch reason distribution
        - Per-vendor match percentage
    """
    session_obj = db.query(ReconciliationSession).filter(
        ReconciliationSession.id == session_id
    ).first()
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found.",
        )

    results = (
        db.query(ReconciliationResult)
        .filter(ReconciliationResult.session_id == session_id)
        .all()
    )

    if not results:
        return {
            "total_invoices": 0,
            "total_reconciled": 0,
            "total_probable": 0,
            "total_mismatches": 0,
            "reconciliation_percentage": 0.0,
            "total_itc_amount": 0.0,
            "potential_itc_loss": 0.0,
            "top_vendors": [],
            "monthly_trend": [],
            "mismatch_reasons": [],
            "vendor_mismatch_percentage": [],
        }

    total_invoices = len(results)
    total_reconciled = sum(1 for r in results if r.match_category in _RECONCILED)
    total_probable = sum(1 for r in results if r.match_category == "Probable Match")
    total_mismatches = sum(1 for r in results if r.match_category in _MISMATCHED)

    reconciliation_pct = round(total_reconciled / total_invoices * 100, 2) if total_invoices else 0.0

    total_itc = round(sum((r.total_gst or 0.0) for r in results if r.match_category in _RECONCILED), 2)
    potential_loss = round(sum((r.total_gst or 0.0) for r in results if r.match_category in _MISMATCHED), 2)

    # --- Top vendors by ITC amount (all categories) ---
    vendor_amounts: dict = defaultdict(lambda: {"amount": 0.0, "count": 0})
    for r in results:
        v = r.vendor_name or "Unknown"
        vendor_amounts[v]["amount"] += r.total_gst or 0.0
        vendor_amounts[v]["count"] += 1
    top_vendors = sorted(
        [{"vendor": k, "amount": round(v["amount"], 2), "count": v["count"]}
         for k, v in vendor_amounts.items()],
        key=lambda x: x["amount"],
        reverse=True,
    )[:10]

    # --- Monthly trend ---
    month_reconciled: dict = defaultdict(int)
    month_mismatched: dict = defaultdict(int)
    for r in results:
        month = (r.invoice_date or "Unknown")[:7] if r.invoice_date else "Unknown"
        # Normalize to YYYY-MM if in DD-MM-YYYY format
        parts = (r.invoice_date or "").split("-")
        if len(parts) == 3 and len(parts[2]) == 4:
            month = f"{parts[2]}-{parts[1]}"
        elif len(parts) == 3 and len(parts[0]) == 4:
            month = f"{parts[0]}-{parts[1]}"
        else:
            month = r.invoice_date[:7] if r.invoice_date and len(r.invoice_date) >= 7 else "Unknown"

        if r.match_category in _RECONCILED:
            month_reconciled[month] += 1
        else:
            month_mismatched[month] += 1

    all_months = sorted(set(list(month_reconciled.keys()) + list(month_mismatched.keys())))
    monthly_trend = [
        {
            "month": m,
            "reconciled": month_reconciled.get(m, 0),
            "mismatched": month_mismatched.get(m, 0),
        }
        for m in all_months
    ]

    # --- Mismatch reasons ---
    reason_counts: dict = defaultdict(int)
    for r in results:
        if r.mismatch_reason:
            for reason in r.mismatch_reason.split(";"):
                reason = reason.strip()
                if reason:
                    reason_counts[reason] += 1
    mismatch_reasons = sorted(
        [{"reason": k, "count": v} for k, v in reason_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    # --- Per-vendor match percentage ---
    vendor_totals: dict = defaultdict(lambda: {"total": 0, "matched": 0})
    for r in results:
        v = r.vendor_name or "Unknown"
        vendor_totals[v]["total"] += 1
        if r.match_category in _RECONCILED:
            vendor_totals[v]["matched"] += 1
    vendor_match_pct = [
        {
            "vendor": v,
            "match_pct": round(d["matched"] / d["total"] * 100, 2) if d["total"] else 0.0,
        }
        for v, d in vendor_totals.items()
    ]
    vendor_match_pct.sort(key=lambda x: x["match_pct"])

    return {
        "total_invoices": total_invoices,
        "total_reconciled": total_reconciled,
        "total_probable": total_probable,
        "total_mismatches": total_mismatches,
        "reconciliation_percentage": reconciliation_pct,
        "total_itc_amount": total_itc,
        "potential_itc_loss": potential_loss,
        "top_vendors": top_vendors,
        "monthly_trend": monthly_trend,
        "mismatch_reasons": mismatch_reasons,
        "vendor_mismatch_percentage": vendor_match_pct,
    }
