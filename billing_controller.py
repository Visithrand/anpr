import threading, time, os, requests
from relay_controller import barrier

BILLING_MODE = os.getenv("BILLING_MODE", "auto")  
# "auto" = test mode, accepts after delay
# "api"  = production, waits for 3rd party API

BILLING_API_URL = os.getenv("BILLING_API_URL", "")
AUTO_ACCEPT_DELAY = int(os.getenv("AUTO_ACCEPT_DELAY", 5))  # seconds


def billing_flow(plate_text: str, record: dict):
    """
    Entry billing flow.
    Since the entry gate should open for ALL vehicles immediately,
    we just open the barrier directly without waiting for billing.
    Billing verification happens only at EXIT via SAP.
    """
    _open_barrier_immediately(plate_text, record)


def _open_barrier_immediately(plate_text: str, record: dict):
    """Open entry barrier immediately for all vehicles."""
    print(f"[BILLING] ✅ Opening entry barrier immediately for {plate_text}")
    barrier.open_barrier(gate_type="entry", duration_ms=3000)


def _open_barrier_and_log(plate_text: str, record: dict):
    """Triggers relay and updates record status to 'cleared'"""
    barrier.open_barrier(gate_type="entry", duration_ms=3000)
    # Update DB record status to cleared
    try:
        from backend.utils.database import SessionLocal
        from backend.models.models import Entry
        with SessionLocal() as db:
            entry = db.query(Entry).filter(Entry.id == record.get("entry_id")).first()
            if entry:
                entry.payment_status = "PAID"
                if entry.billing:
                    entry.billing.paid = True
                db.commit()
                print(f"[BILLING] DB updated for {plate_text} to PAID")
    except Exception as e:
        print(f"[BILLING] DB update error: {e}")
