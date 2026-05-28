"""
backend/routes/reports.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Vehicle entry/exit reports with summary statistics and export support.

Endpoints:
  GET /reports/          → paginated report data with billing info
  GET /reports/summary   → aggregate stats (totals, revenue)
  GET /reports/export    → CSV export (no pagination)
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import csv
import io

from backend.utils.database import get_db
from backend.models.models import Entry, Vehicle, Billing

router = APIRouter(prefix="/reports", tags=["reports"])


def _get_start_date(timeframe: str) -> datetime:
    now = datetime.utcnow()
    if timeframe == "week":
        return now - timedelta(days=7)
    elif timeframe == "month":
        return now - timedelta(days=30)
    else:  # default: today
        return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _format_duration(entry_time, exit_time) -> str:
    if not exit_time or not entry_time:
        return "-"
    diff = exit_time - entry_time
    total_seconds = int(diff.total_seconds())
    if total_seconds < 0:
        return "-"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _serialize_entry(e: Entry, index: int) -> Dict[str, Any]:
    billing_amount = None
    billing_paid = False
    billing_reference = None

    if e.billing:
        billing_amount = e.billing.amount
        billing_paid = e.billing.paid
        billing_reference = e.billing.billing_reference

    return {
        "sno": index + 1,
        "transaction_id": e.transaction_id or f"TXN-{e.id:06d}",
        "plate_number": e.plate_number or "-",
        "entry_time": e.entry_time.isoformat() if e.entry_time else None,
        "exit_time": e.exit_time.isoformat() if e.exit_time else None,
        "stayed": _format_duration(e.entry_time, e.exit_time),
        "status": e.status or "IN",
        "payment_status": e.payment_status or "PENDING",
        "location": e.location or "Main Gate",
        "lane": e.lane or "Lane 1",
        "vehicle_type": e.vehicle_type or "Unknown",
        "billing_amount": billing_amount,
        "billing_paid": billing_paid,
        "billing_reference": billing_reference or "-",
        "plate_image_path": e.plate_image_path or "",
        "vehicle_image_path": e.vehicle_image_path or "",
    }


@router.get("/")
def get_reports(
    timeframe: str = Query("today", description="today | week | month"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="IN | OUT | (empty = all)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return paginated vehicle entry/exit records with billing data.
    """
    start_date = _get_start_date(timeframe)

    query = db.query(Entry).filter(Entry.entry_time >= start_date)

    if status and status in ("IN", "OUT"):
        query = query.filter(Entry.status == status)

    total = query.count()
    entries = (
        query.order_by(Entry.entry_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = [_serialize_entry(e, (page - 1) * page_size + i) for i, e in enumerate(entries)]

    return {
        "data": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),  # ceiling division
    }


@router.get("/summary")
def get_report_summary(
    timeframe: str = Query("today"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return aggregate stats: vehicle counts, revenue, avg duration.
    """
    start_date = _get_start_date(timeframe)

    total_entries = db.query(Entry).filter(Entry.entry_time >= start_date).count()
    total_exits = db.query(Entry).filter(
        Entry.exit_time >= start_date, Entry.status == "OUT"
    ).count()
    currently_inside = db.query(Entry).filter(Entry.status == "IN").count()

    # Revenue from confirmed billing in the timeframe
    revenue_row = (
        db.query(func.coalesce(func.sum(Billing.amount), 0.0))
        .join(Entry, Billing.entry_id == Entry.id)
        .filter(Billing.paid == True, Entry.entry_time >= start_date)
        .scalar()
    )
    total_revenue = float(revenue_row or 0.0)

    # Average duration of completed trips
    completed = (
        db.query(Entry)
        .filter(
            Entry.entry_time >= start_date,
            Entry.status == "OUT",
            Entry.exit_time.isnot(None),
        )
        .all()
    )
    avg_stay_minutes = 0.0
    if completed:
        total_mins = sum(
            (e.exit_time - e.entry_time).total_seconds() / 60
            for e in completed
            if e.exit_time and e.entry_time
        )
        avg_stay_minutes = round(total_mins / len(completed), 1)

    return {
        "timeframe": timeframe,
        "total_entries": total_entries,
        "total_exits": total_exits,
        "currently_inside": currently_inside,
        "total_revenue": round(total_revenue, 2),
        "avg_stay_minutes": avg_stay_minutes,
        "completed_trips": len(completed),
    }


@router.get("/export")
def export_csv(
    timeframe: str = Query("today"),
    db: Session = Depends(get_db),
):
    """
    Stream a CSV file of all records for the given timeframe.
    """
    start_date = _get_start_date(timeframe)
    entries = (
        db.query(Entry)
        .filter(Entry.entry_time >= start_date)
        .order_by(Entry.entry_time.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "S.No", "Transaction ID", "Plate Number",
        "Entry Time", "Exit Time", "Duration",
        "Status", "Payment Status", "Billing Amount",
        "Location", "Lane",
    ])

    for i, e in enumerate(entries):
        billing_amount = e.billing.amount if e.billing else ""
        writer.writerow([
            i + 1,
            e.transaction_id or f"TXN-{e.id:06d}",
            e.plate_number or "",
            e.entry_time.strftime("%Y-%m-%d %H:%M:%S") if e.entry_time else "",
            e.exit_time.strftime("%Y-%m-%d %H:%M:%S") if e.exit_time else "",
            _format_duration(e.entry_time, e.exit_time),
            e.status or "",
            e.payment_status or "PENDING",
            billing_amount,
            e.location or "",
            e.lane or "",
        ])

    output.seek(0)
    label = {"today": "Daily", "week": "Weekly", "month": "Monthly"}.get(timeframe, "Report")
    filename = f"ANPR_{label}_Report_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
