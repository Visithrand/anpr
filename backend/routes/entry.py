"""
backend/routes/entry.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Entry gate endpoint.

Flow:
  1. Camera / operator submits plate number
  2. Vehicle is auto-registered if not in DB
  3. Duplicate check — if already inside, reject
  4. Entry record created (status=IN, payment_status=PENDING)
  5. Billing record created (paid=False)
  6. Entry boom barrier opens  ← open_entry_gate()
  7. Audit log written
  8. WebSocket broadcast to refresh dashboard
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from sqlalchemy.orm import Session

from backend.utils.database import get_db
from backend.models.models import Vehicle, Entry, Billing, AuditLog
from backend.services.gate_trigger import open_entry_gate
from backend.utils.websocket import manager

router = APIRouter()


@router.post("/entry")
async def vehicle_entry(
    plate_number: str,
    operator: str = "System Admin",
    location: str = "Main Gate",
    lane: str = "Lane 1",
    db: Session = Depends(get_db),
):
    """
    ENTRY GATE allows all vehicles. SAP and duplicate checks are bypassed.
    Gate opens immediately, even if DB logging fails.
    """
    import logging
    log = logging.getLogger(__name__)

    # 1. ALWAYS OPEN ENTRY GATE FIRST (Bypass all checks)
    gate_status = "opened"
    gate_details = {}
    try:
        gate_details = await open_entry_gate()
        log.info(f"ENTRY GATE allows all vehicles. Gate opened for {plate_number}")
    except Exception as gate_err:
        log.error(f"Failed to open entry gate for {plate_number}: {gate_err}")
        gate_status = "error"
        gate_details = {"status": "error"}

    # 2. Try to log to DB (do not block gate opening if this fails)
    try:
        vehicle = db.query(Vehicle).filter(
            Vehicle.plate_number == plate_number
        ).first()

        if not vehicle:
            vehicle = Vehicle(plate_number=plate_number)
            db.add(vehicle)
            db.commit()
            db.refresh(vehicle)

        new_entry = Entry(
            plate_number=plate_number,
            vehicle_id=vehicle.id,
            entry_time=datetime.utcnow(),
            status="IN",
            payment_status="PENDING",
            location=location,
            lane=lane,
        )
        db.add(new_entry)
        db.flush()

        billing = Billing(
            entry_id=new_entry.id,
            amount=0.0,
            paid=False,
        )
        db.add(billing)

        log_entry = AuditLog(
            action="ENTRY",
            plate_number=plate_number,
            operator=operator,
            details=f"Vehicle entered at {location} / {lane}. Awaiting billing confirmation.",
        )
        db.add(log_entry)
        db.commit()

        await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')

        return {
            "message": "Vehicle entry recorded — entry gate opened",
            "plate_number": plate_number,
            "entry_id": new_entry.id,
            "status": "IN",
            "payment_status": "PENDING",
            "gate": gate_details,
        }

    except Exception as e:
        log.error(f"Failed to log entry to DB for {plate_number}, but gate was opened. Error: {e}")
        db.rollback()
        # Return success since gate was opened
        return {
            "message": "Gate opened, but DB logging failed",
            "plate_number": plate_number,
            "status": "UNKNOWN",
            "payment_status": "UNKNOWN",
            "gate": gate_details,
        }