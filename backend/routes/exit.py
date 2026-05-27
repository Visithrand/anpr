"""
backend/routes/exit.py
~~~~~~~~~~~~~~~~~~~~~~~~
Exit gate endpoint — Third-party payment verification flow.

Flow:
  1. Camera / operator submits plate number at exit gate
  2. Find active Entry for this plate (status=IN)
  3. Query external Billing API: GET {BILLING_API_URL}/payment/status?plate=XX
  4a. Payment confirmed (paid=True):
      → Entry status = OUT, payment_status = PAID
      → Billing record updated: paid=True, amount, reference
      → open_exit_gate() called → boom barrier opens
      → Audit log: EXIT_APPROVED
      → Return success + gate status
  4b. Payment NOT confirmed (paid=False):
      → Entry stays IN, gate stays closed
      → Audit log: EXIT_DENIED
      → Return 402 Payment Required with reason
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from sqlalchemy.orm import Session

from backend.utils.database import get_db
from backend.models.models import Vehicle, Entry, Billing, AuditLog
from backend.services.gate_trigger import open_exit_gate
from backend.services.billing_service import check_payment_status
from backend.utils.websocket import manager

router = APIRouter()


@router.post("/exit")
async def vehicle_exit(
    plate_number: str,
    operator: str = "System Admin",
    bypass_payment: bool = False,
    trigger_gate: bool = True,
    db: Session = Depends(get_db),
):
    """
    Process vehicle exit.
    Gate only opens if the external billing system confirms payment,
    unless bypass_payment is set to True (Admin Override).
    """
    try:
        # 1. Find vehicle
        vehicle = db.query(Vehicle).filter(
            Vehicle.plate_number == plate_number
        ).first()

        if not vehicle:
            raise HTTPException(
                status_code=404,
                detail=f"Vehicle {plate_number} not registered in the system"
            )

        # 2. Find active entry
        entry = db.query(Entry).filter(
            Entry.vehicle_id == vehicle.id,
            Entry.status == "IN"
        ).first()

        if not entry:
            raise HTTPException(
                status_code=400,
                detail=f"No active entry found for vehicle {plate_number}"
            )

        # 3. Check if already marked as PAID locally, bypassed, or query external Billing API
        if bypass_payment or entry.payment_status == "PAID" or (entry.billing and entry.billing.paid):
            payment = {
                "paid": True,
                "amount": entry.billing.amount if entry.billing else 0.0,
                "reference": "BYPASS" if bypass_payment else (entry.billing.billing_reference if entry.billing else "LOCAL"),
                "message": "Payment bypassed by Admin Override" if bypass_payment else "Payment verified locally via database status",
                "api_reachable": True
            }
        else:
            payment = await check_payment_status(plate_number)

        if not payment["paid"]:
            # ---- PAYMENT NOT CONFIRMED → Gate stays closed ----
            audit = AuditLog(
                action="EXIT_DENIED",
                plate_number=plate_number,
                operator=operator,
                details=(
                    f"Exit denied — payment not confirmed. "
                    f"Billing API reachable: {payment['api_reachable']}. "
                    f"Reason: {payment['message']}"
                ),
            )
            db.add(audit)
            db.commit()

            await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')

            raise HTTPException(
                status_code=402,
                detail={
                    "message": "Exit denied — payment not yet confirmed by billing system",
                    "plate_number": plate_number,
                    "payment_status": "PENDING",
                    "gate": "closed",
                    "reason": payment["message"],
                    "api_reachable": payment["api_reachable"],
                },
            )

        # ---- PAYMENT CONFIRMED → Open gate ----
        exit_time = datetime.utcnow()

        # Update entry
        entry.exit_time = exit_time
        entry.status = "OUT"
        entry.billed = True
        entry.payment_status = "PAID"

        # Update billing record
        billing = entry.billing
        if billing:
            billing.paid = True
            billing.amount = payment["amount"]
            billing.billing_reference = payment["reference"]
        else:
            # Safety: create billing record if somehow missing
            billing = Billing(
                entry_id=entry.id,
                amount=payment["amount"],
                paid=True,
                billing_reference=payment["reference"],
            )
            db.add(billing)

        # Audit log
        duration_min = round((exit_time - entry.entry_time).total_seconds() / 60, 1)
        audit = AuditLog(
            action="EXIT_APPROVED",
            plate_number=plate_number,
            operator=operator,
            details=(
                f"Vehicle exited. Duration: {duration_min} min. "
                f"Amount: {payment['amount']}. "
                f"Ref: {payment['reference']}. "
                f"{payment['message']}"
            ),
        )
        db.add(audit)
        db.commit()

        # Trigger exit gate
        gate = None
        if trigger_gate:
            gate = await open_exit_gate()

        # Broadcast dashboard refresh
        await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')

        return {
            "message": "Payment confirmed — exit gate opened",
            "plate_number": plate_number,
            "status": "OUT",
            "payment_status": "PAID",
            "duration_minutes": duration_min,
            "amount": payment["amount"],
            "billing_reference": payment["reference"],
            "billing_message": payment["message"],
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
