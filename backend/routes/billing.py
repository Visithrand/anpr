"""
backend/routes/billing.py
~~~~~~~~~~~~~~~~~~~~~~~~~
External billing webhook endpoint.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.utils.database import get_db
from backend.models.models import Entry, Billing, AuditLog
from backend.services.gate_service import gate_service

router = APIRouter(prefix="/api", tags=["billing"])

class BillingAckPayload(BaseModel):
    plate_number: str
    transaction_id: str
    status: str
    amount: Optional[float] = 0.0
    timestamp: Optional[str] = None

@router.post("/billing-ack")
def receive_billing_ack(payload: BillingAckPayload, db: Session = Depends(get_db)):
    # Find active entry for this plate (status == "IN")
    entry = db.query(Entry).filter(
        Entry.plate_number == payload.plate_number,
        Entry.status == "IN"
    ).order_by(Entry.id.desc()).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Active entry not found for this plate")

    # Update payment status
    entry.payment_status = payload.status
    
    # Update Billing table if it exists, otherwise create
    billing = db.query(Billing).filter(Billing.entry_id == entry.id).first()
    if not billing:
        billing = Billing(entry_id=entry.id)
        db.add(billing)
        
    billing.billing_reference = payload.transaction_id
    billing.amount = payload.amount
    if payload.status.upper() == "PAID":
        billing.paid = True
        
    gate_opened = False
    if payload.status.upper() == "PAID":
        # Trigger gate open
        gate_service.open_gate()
        gate_opened = True
        
        # Mark as OUT
        entry.exit_time = datetime.utcnow()
        entry.status = "OUT"
        
    # Log to AuditLog
    audit = AuditLog(
        action="BILLING_ACK",
        plate_number=payload.plate_number,
        details=f"Received {payload.status} for txn {payload.transaction_id}. Gate opened: {gate_opened}"
    )
    db.add(audit)
        
    db.commit()
    
    return {"message": "Billing ACK processed successfully", "gate_opened": gate_opened}
