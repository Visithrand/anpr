from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from sqlalchemy.orm import Session

from backend.utils.database import get_db
from backend.models.models import Vehicle, Entry, Billing, AuditLog
from backend.utils.websocket import manager

router = APIRouter()

RATE_PER_HOUR_STANDARD = 20     # ₹20/hr normal rate
RATE_PER_HOUR_PEAK = 30         # ₹30/hr during peak hours (9 AM - 6 PM)
DAILY_CAP = 200                 # Max ₹200/day
PENALTY_HOURS = 24              # Overstay threshold in hours
PENALTY_AMOUNT = 500            # ₹500 penalty for overstay
FREE_MINUTES = 15               # First 15 minutes are free


def calculate_amount(entry_time: datetime, exit_time: datetime) -> tuple[float, float, str]:
    """
    Smart billing with gov-style rules:
    - First 15 min free
    - Peak hour pricing (9 AM - 6 PM IST = 3:30–12:30 UTC)
    - Daily cap at ₹200
    - ₹500 penalty for overstay beyond 24 hours
    Returns (amount, duration_minutes, billing_notes)
    """
    duration_seconds = (exit_time - entry_time).total_seconds()
    duration_minutes = duration_seconds / 60.0
    duration_hours = duration_seconds / 3600.0

    notes = []

    # Rule 1: First 15 minutes free
    if duration_minutes <= FREE_MINUTES:
        notes.append("First 15 min free — ₹0 charged")
        return 0.0, duration_minutes, "; ".join(notes)

    # Rule 2: Penalty for overstay beyond 24 hours
    if duration_hours > PENALTY_HOURS:
        notes.append(f"Overstay penalty applied (>{PENALTY_HOURS}hrs)")
        return float(PENALTY_AMOUNT), duration_minutes, "; ".join(notes)

    # Rule 3: Peak hour detection (entry hour in UTC, 3:30–12:30 UTC = 9–18 IST)
    entry_hour = entry_time.hour
    is_peak = 3 <= entry_hour < 13  # 3:30 AM–12:30 PM UTC == 9 AM–6 PM IST
    rate = RATE_PER_HOUR_PEAK if is_peak else RATE_PER_HOUR_STANDARD

    if is_peak:
        notes.append(f"Peak hour rate applied (₹{rate}/hr)")
    else:
        notes.append(f"Standard rate applied (₹{rate}/hr)")

    # Rule 4: Calculate and cap
    raw_amount = (duration_hours * rate)
    amount = min(raw_amount, DAILY_CAP)

    if raw_amount > DAILY_CAP:
        notes.append(f"Daily cap (₹{DAILY_CAP}) applied")

    return round(amount, 2), round(duration_minutes, 2), "; ".join(notes)


@router.post("/exit")
async def vehicle_exit(plate_number: str, operator: str = "System Admin", db: Session = Depends(get_db)):
    try:
        vehicle = db.query(Vehicle).filter(
            Vehicle.plate_number == plate_number
        ).first()

        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        entry = db.query(Entry).filter(
            Entry.vehicle_id == vehicle.id,
            Entry.status == "IN"
        ).first()

        if not entry:
            raise HTTPException(status_code=400, detail="No active entry found")

        exit_time = datetime.utcnow()
        entry.exit_time = exit_time
        entry.status = "OUT"

        amount, duration_minutes, billing_notes = calculate_amount(entry.entry_time, exit_time)

        bill = Billing(
            entry_id=entry.id,
            duration_minutes=duration_minutes,
            amount=amount
        )
        db.add(bill)

        # Audit log
        log = AuditLog(
            action="EXIT",
            plate_number=plate_number,
            operator=operator,
            details=f"Ticket {entry.ticket_id}. Duration: {duration_minutes:.1f} min. Amount: ₹{amount}. {billing_notes}"
        )
        db.add(log)
        db.commit()

        # Broadcast real-time update
        await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')

        return {
            "message": "Vehicle exited",
            "plate_number": plate_number,
            "ticket_id": entry.ticket_id,
            "duration_minutes": round(duration_minutes, 2),
            "amount": amount,
            "billing_notes": billing_notes,
            "status": "OUT"
        }

    except HTTPException as he:
        db.rollback()
        raise he

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
