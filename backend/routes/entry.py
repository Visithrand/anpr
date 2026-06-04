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
    Register vehicle entry and open the entry boom barrier.
    Called by admin panel or directly by the ANPR camera pipeline.
    """
    try:
        # 1. Auto-register vehicle if not in DB
        vehicle = db.query(Vehicle).filter(
            Vehicle.plate_number == plate_number
        ).first()

        if not vehicle:
            vehicle = Vehicle(plate_number=plate_number)
            db.add(vehicle)
            db.commit()
            db.refresh(vehicle)

        # 2. Create entry record (allow all vehicles — no duplicate check)
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
        db.flush()  # get new_entry.id without full commit

        # 4. Create billing record — amount=0.0 until third-party confirms
        billing = Billing(
            entry_id=new_entry.id,
            amount=0.0,
            paid=False,
        )
        db.add(billing)

        # 5. Audit log
        log_entry = AuditLog(
            action="ENTRY",
            plate_number=plate_number,
            operator=operator,
            details=f"Vehicle entered at {location} / {lane}. Awaiting billing confirmation.",
        )
        db.add(log_entry)
        db.commit()

        # 6. Trigger entry gate open
        gate = await open_entry_gate()

        # 7. Broadcast real-time dashboard update
        await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')

        return {
            "message": "Vehicle entry recorded — entry gate opened",
            "plate_number": plate_number,
            "entry_id": new_entry.id,
            "status": "IN",
            "payment_status": "PENDING",
            "gate": gate,
        }

    except HTTPException as he:
        db.rollback()
        raise he

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))