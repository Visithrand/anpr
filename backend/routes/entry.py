from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

from backend.utils.database import get_db
from backend.models.models import Vehicle, Entry, AuditLog
from backend.utils.websocket import manager

router = APIRouter()

def generate_ticket_id() -> str:
    """Generate a unique government-style ticket ID."""
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = str(uuid.uuid4())[:6].upper()
    return f"TKT-{ts}-{suffix}"


@router.post("/entry")
async def vehicle_entry(plate_number: str, operator: str = "System Admin", db: Session = Depends(get_db)):
    try:
        vehicle = db.query(Vehicle).filter(
            Vehicle.plate_number == plate_number
        ).first()

        # Auto-register vehicle if not exists
        if not vehicle:
            vehicle = Vehicle(plate_number=plate_number)
            db.add(vehicle)
            db.commit()
            db.refresh(vehicle)

        # Check if already inside
        existing_entry = db.query(Entry).filter(
            Entry.vehicle_id == vehicle.id,
            Entry.status == "IN"
        ).first()

        if existing_entry:
            raise HTTPException(status_code=400, detail="Vehicle already inside")

        ticket_id = generate_ticket_id()
        new_entry = Entry(
            ticket_id=ticket_id,
            vehicle_id=vehicle.id,
            entry_time=datetime.utcnow(),
            status="IN"
        )
        db.add(new_entry)

        # Audit log
        log = AuditLog(
            action="ENTRY",
            plate_number=plate_number,
            operator=operator,
            details=f"Ticket {ticket_id} issued. Vehicle entered parking."
        )
        db.add(log)
        db.commit()

        # Broadcast real-time update
        await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')

        return {
            "message": "Vehicle entry recorded",
            "plate_number": plate_number,
            "ticket_id": ticket_id,
            "status": "IN"
        }

    except HTTPException as he:
        db.rollback()
        raise he

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))