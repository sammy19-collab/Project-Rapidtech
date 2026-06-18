from collections import defaultdict
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from models import ReconciliationResult, ReconciliationSession

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

fmt_inr = lambda n: round(float(n or 0), 2)
_f = lambda v: float(v or 0)


@router.get("/{session_id}")
def get_dashboard(session_id: int, month_year: str = Query(None), branch: str = Query(None), db: Session = Depends(get_db)):
    session_obj = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
    if not session_obj:
        raise HTTPException(404, "Session not found")

    all_results = db.query(ReconciliationResult).filter(ReconciliationResult.session_id == session_id).all()
    if not all_results:
        raise HTTPException(404, "No reconciliation results found. Run reconciliation first.")

    # Available branches and months always computed from full results
    available_branches = sorted({r.branch for r in all_results if r.branch})
    available_months   = sorted({r.month_year for r in all_results if r.month_year})

    # Apply filters
    results = all_results
    if branch:
        results = [r for r in results if r.branch == branch]
    if month_year:
        results = [r for r in results if r.month_year == month_year]

    reconciled = [r for r in results if r.match_category in ("Exact Match", "Strong Match")]
    probable   = [r for r in results if r.match_category == "Probable Match"]
    manual     = [r for r in results if r.match_category == "Manual Review"]
    miss_books = [r for r in results if r.match_category == "Missing in Books"]

    books_entries  = [r for r in results if r.books_entry_id]
    total_invoices = len(books_entries)
    recon_pct      = round(len(reconciled) / total_invoices * 100, 1) if total_invoices else 0
    total_itc      = sum(_f(r.total_gst) for r in reconciled)
    potential_loss = sum(_f(r.total_gst) for r in manual)

    # Month-wise breakdown (respects branch filter, ignores month filter)
    base = [r for r in all_results if (not branch or r.branch == branch)]
    month_breakdown = defaultdict(lambda: {"reconciled": 0, "probable": 0, "manual": 0, "missing_books": 0, "itc": 0.0})
    for r in base:
        m = r.month_year or "Unknown"
        if r.match_category in ("Exact Match", "Strong Match"):
            month_breakdown[m]["reconciled"] += 1
            month_breakdown[m]["itc"] += _f(r.total_gst)
        elif r.match_category == "Probable Match":
            month_breakdown[m]["probable"] += 1
        elif r.match_category == "Manual Review":
            month_breakdown[m]["manual"] += 1
        elif r.match_category == "Missing in Books":
            month_breakdown[m]["missing_books"] += 1

    monthly_trend = [
        {"month": m, **{k: round(v, 2) if isinstance(v, float) else v for k, v in stats.items()}}
        for m, stats in sorted(month_breakdown.items())
    ]

    # Vendor stats
    vendor_amounts = defaultdict(float)
    vendor_totals  = defaultdict(int)
    vendor_matched = defaultdict(int)
    for r in results:
        if r.books_entry_id:
            v = r.vendor_name or "Unknown"
            vendor_amounts[v] += _f(r.taxable_value)
            vendor_totals[v]  += 1
            if r.match_category in ("Exact Match", "Strong Match"):
                vendor_matched[v] += 1

    top_vendors = sorted(
        [{"vendor": k, "amount": round(v, 2), "count": vendor_totals[k]} for k, v in vendor_amounts.items()],
        key=lambda x: x["amount"], reverse=True
    )[:10]

    vendor_mismatch = [
        {"vendor": v, "total": vendor_totals[v], "matched": vendor_matched[v],
         "match_pct": round(vendor_matched[v] / vendor_totals[v] * 100, 1) if vendor_totals[v] else 0}
        for v in vendor_totals
    ]

    reason_counts = defaultdict(int)
    for r in results:
        if r.mismatch_reason:
            for part in r.mismatch_reason.split(";"):
                reason_counts[part.strip()] += 1
    mismatch_reasons = [{"reason": k, "count": v} for k, v in sorted(reason_counts.items(), key=lambda x: -x[1])]

    return {
        "branch": session_obj.branch,
        "recon_month": session_obj.recon_month,
        "recon_year": session_obj.recon_year,
        "active_filter": month_year,
        "active_branch": branch,
        "available_months": available_months,
        "available_branches": available_branches,
        "total_invoices": total_invoices,
        "total_reconciled": len(reconciled),
        "total_probable": len(probable),
        "total_manual_review": len(manual),
        "total_missing_in_books": len(miss_books),
        "reconciliation_percentage": recon_pct,
        "total_itc_amount": fmt_inr(total_itc),
        "potential_itc_loss": fmt_inr(potential_loss),
        "top_vendors": top_vendors,
        "monthly_trend": monthly_trend,
        "mismatch_reasons": mismatch_reasons,
        "vendor_mismatch_percentage": vendor_mismatch,
    }
