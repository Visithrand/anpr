"""
backend/routes/billing.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Billing webhook and status endpoints.

Endpoints:
  POST /billing/confirm
      Called BY the third-party billing system to confirm a payment.
      Updates the vehicle's billing record and payment status.
      If the vehicle is waiting at the exit gate, this allows it to exit.

  GET /billing/status/{plate_number}
      Query the current payment status for a vehicle plate.

  GET /billing/history
      List all billing records (paginated).
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from backend.utils.database import get_db
from backend.models.models import Vehicle, Entry, Billing, AuditLog
from backend.utils.websocket import manager

router = APIRouter(prefix="/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class PaymentConfirmRequest(BaseModel):
    plate_number: str
    amount: float
    reference: str                     # Transaction reference ID from billing system
    operator: Optional[str] = "Billing-System"
    message: Optional[str] = "Payment confirmed by billing system"


# ---------------------------------------------------------------------------
# POST /billing/confirm — Third-party payment webhook
# ---------------------------------------------------------------------------

@router.post("/confirm")
async def confirm_payment(
    payload: PaymentConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Called by the external billing / POS system when a payment is completed.

    Updates:
      - Billing.paid = True
      - Billing.amount = payload.amount
      - Billing.billing_reference = payload.reference
      - Entry.payment_status = PAID

    After this call, when the vehicle approaches the exit gate, the system
    will detect payment=confirmed and open the gate.
    """
    # Find vehicle
    vehicle = db.query(Vehicle).filter(
        Vehicle.plate_number == payload.plate_number
    ).first()

    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail=f"Vehicle {payload.plate_number} not found"
        )

    # Find active entry
    entry = db.query(Entry).filter(
        Entry.vehicle_id == vehicle.id,
        Entry.status == "IN",
    ).first()

    if not entry:
        raise HTTPException(
            status_code=400,
            detail=f"No active entry found for {payload.plate_number}. Vehicle may have already exited."
        )

    # Update or create billing record
    billing = entry.billing
    if billing:
        billing.paid = True
        billing.amount = payload.amount
        billing.billing_reference = payload.reference
    else:
        billing = Billing(
            entry_id=entry.id,
            amount=payload.amount,
            paid=True,
            billing_reference=payload.reference,
        )
        db.add(billing)

    # Mark entry payment as PAID
    entry.payment_status = "PAID"

    # Audit log
    audit = AuditLog(
        action="PAYMENT_RECEIVED",
        plate_number=payload.plate_number,
        operator=payload.operator,
        details=(
            f"Payment confirmed by billing system. "
            f"Amount: {payload.amount}. "
            f"Ref: {payload.reference}. "
            f"{payload.message}"
        ),
    )
    db.add(audit)
    db.commit()

    # Broadcast so dashboard shows updated payment status
    await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')

    return {
        "message": "Payment confirmed successfully",
        "plate_number": payload.plate_number,
        "payment_status": "PAID",
        "amount": payload.amount,
        "reference": payload.reference,
        "note": "Vehicle can now exit — gate will open on next exit scan",
    }


# ---------------------------------------------------------------------------
# GET /billing/status/{plate_number} — Check payment status
# ---------------------------------------------------------------------------

@router.get("/status/{plate_number}")
def get_payment_status(plate_number: str, db: Session = Depends(get_db)):
    """
    Returns the current payment and entry status for a vehicle.
    Can be polled by the exit gate camera controller or operator dashboard.
    """
    vehicle = db.query(Vehicle).filter(
        Vehicle.plate_number == plate_number
    ).first()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    entry = db.query(Entry).filter(
        Entry.vehicle_id == vehicle.id,
        Entry.status == "IN",
    ).first()

    if not entry:
        # Check last completed entry
        last_entry = (
            db.query(Entry)
            .filter(Entry.vehicle_id == vehicle.id)
            .order_by(Entry.entry_time.desc())
            .first()
        )
        if last_entry:
            return {
                "plate_number": plate_number,
                "status": last_entry.status,
                "payment_status": last_entry.payment_status,
                "message": "Vehicle has already exited",
            }
        raise HTTPException(status_code=404, detail="No entry record found")

    return {
        "plate_number": plate_number,
        "entry_id": entry.id,
        "status": entry.status,
        "payment_status": entry.payment_status,
        "entry_time": entry.entry_time.isoformat() if entry.entry_time else None,
        "billed": entry.billed,
        "billing": {
            "paid": entry.billing.paid if entry.billing else False,
            "amount": entry.billing.amount if entry.billing else 0.0,
            "reference": entry.billing.billing_reference if entry.billing else None,
        } if entry.billing else None,
        "can_exit": entry.payment_status == "PAID",
    }


# ---------------------------------------------------------------------------
# GET /billing/history — All billing records
# ---------------------------------------------------------------------------

@router.get("/history")
def billing_history(
    limit: int = 50,
    paid_only: bool = False,
    db: Session = Depends(get_db),
):
    """Returns billing records, newest first."""
    query = db.query(Billing)
    if paid_only:
        query = query.filter(Billing.paid == True)
    records = query.order_by(Billing.id.desc()).limit(limit).all()

    return [
        {
            "id": b.id,
            "entry_id": b.entry_id,
            "plate_number": b.entry.plate_number if b.entry else None,
            "amount": b.amount,
            "paid": b.paid,
            "billing_reference": b.billing_reference,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in records
    ]
