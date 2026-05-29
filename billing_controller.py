import threading, time, os, requests
from relay_controller import barrier

BILLING_MODE = os.getenv("BILLING_MODE", "auto")  
# "auto" = test mode, accepts after delay
# "api"  = production, waits for 3rd party API

BILLING_API_URL = os.getenv("BILLING_API_URL", "")
AUTO_ACCEPT_DELAY = int(os.getenv("AUTO_ACCEPT_DELAY", 5))  # seconds


def billing_flow(plate_text: str, record: dict):
    """
    Main billing entry point.
    In test mode: auto-accepts after delay then opens barrier.
    In API mode: calls 3rd party billing API and waits for confirmation.
    """
    threading.Thread(
        target=_run_billing,
        args=(plate_text, record),
        daemon=True
    ).start()


def _run_billing(plate_text: str, record: dict):
    if BILLING_MODE == "auto":
        _auto_accept(plate_text, record)
    elif BILLING_MODE == "api":
        _api_billing(plate_text, record)


def _auto_accept(plate_text: str, record: dict):
    """TEST MODE — auto accepts billing after delay"""
    print(f"[BILLING] Auto-accepting for {plate_text} in {AUTO_ACCEPT_DELAY}s...")
    time.sleep(AUTO_ACCEPT_DELAY)
    print(f"[BILLING] ✅ Accepted — opening barrier for {plate_text}")
    _open_barrier_and_log(plate_text, record)


def _api_billing(plate_text: str, record: dict):
    """PRODUCTION MODE — calls 3rd party billing API"""
    try:
        payload = {
            "plate_number": plate_text,
            "detected_at": record.get("detected_at"),
            "camera_id": record.get("camera_id"),
        }
        response = requests.post(BILLING_API_URL, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "approved":
                print(f"[BILLING] ✅ API approved — opening barrier for {plate_text}")
                _open_barrier_and_log(plate_text, record)
            else:
                print(f"[BILLING] ❌ API rejected for {plate_text}: {data}")
        else:
            print(f"[BILLING] ❌ API error {response.status_code} for {plate_text}")

    except Exception as e:
        print(f"[BILLING] ❌ Exception for {plate_text}: {e}")


def _open_barrier_and_log(plate_text: str, record: dict):
    """Triggers relay and updates record status to 'cleared'"""
    barrier.open_barrier(relay_num=1, duration_ms=3000)
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
