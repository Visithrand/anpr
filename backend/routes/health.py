"""
backend/routes/health.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
System health and monitoring endpoints.

Endpoints:
  GET /system/health   → comprehensive health check of all subsystems
  GET /system/metrics  → key operational metrics
  GET /vehicle/{plate} → vehicle lookup by plate number
  GET /transactions    → paginated transaction history
"""

from __future__ import annotations

import logging
import platform
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from backend.config import settings
from backend.utils.database import get_db, engine, SessionLocal
from backend.utils.helpers import get_disk_usage, count_files_in_dir
from backend.models.models import Vehicle, Entry, Billing, SystemLog

log = logging.getLogger(__name__)
router = APIRouter(tags=["system"])

# Track application start time
_app_start_time = time.time()


# ---------------------------------------------------------------------------
# GET /system/health
# ---------------------------------------------------------------------------

@router.get("/system/health")
def system_health(db: Session = Depends(get_db)):
    """
    Comprehensive health check of all subsystems.

    Returns the status of:
      - Database connectivity
      - Camera feeds (per-camera health)
      - OCR service
      - Billing API
      - Gate controller
      - System resources (disk, memory)
      - Application uptime
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": round(time.time() - _app_start_time, 1),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "components": {},
    }

    issues = []

    # 1. Database
    try:
        db.execute(text("SELECT 1"))
        pool = engine.pool
        health["components"]["database"] = {
            "status": "healthy",
            "pool_size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "checked_in": pool.checkedin(),
        }
    except Exception as e:
        health["components"]["database"] = {"status": "unhealthy", "error": str(e)}
        issues.append("database")

    # 2. Cameras
    try:
        from backend.routes.live import camera_mgr
        camera_health = camera_mgr.health_report()
        active = sum(1 for c in camera_health if c["running"])
        health["components"]["cameras"] = {
            "status": "healthy" if active > 0 or not settings.camera_defaults else "idle",
            "active_count": active,
            "max_cameras": settings.MAX_CAMERAS,
            "feeds": camera_health,
        }
    except Exception as e:
        health["components"]["cameras"] = {"status": "error", "error": str(e)}
        issues.append("cameras")

    # 3. OCR Service
    try:
        ocr_base = settings.OCR_SERVICE_URL.replace("/ocr", "/")
        resp = httpx.get(ocr_base, timeout=3.0)
        health["components"]["ocr_service"] = {
            "status": "healthy" if resp.status_code == 200 else "degraded",
            "url": settings.OCR_SERVICE_URL,
            "http_status": resp.status_code,
        }
    except Exception as e:
        health["components"]["ocr_service"] = {
            "status": "unreachable",
            "url": settings.OCR_SERVICE_URL,
            "error": str(e),
        }
        issues.append("ocr_service")

    # 4. Billing API
    try:
        billing_url = settings.BILLING_API_URL.rstrip("/")
        resp = httpx.get(f"{billing_url}/", timeout=3.0)
        health["components"]["billing_api"] = {
            "status": "healthy" if resp.status_code < 500 else "degraded",
            "backend": settings.BILLING_BACKEND,
            "url": billing_url,
        }
    except Exception:
        health["components"]["billing_api"] = {
            "status": "unreachable",
            "backend": settings.BILLING_BACKEND,
            "url": settings.BILLING_API_URL,
            "note": "Billing API not reachable — exit gate will deny vehicles",
        }
        # Not a critical issue if using mock backend
        if settings.BILLING_BACKEND != "mock":
            issues.append("billing_api")

    # 5. Gate Controller
    try:
        gate_url = settings.GATE_API_URL.rstrip("/")
        resp = httpx.get(f"{gate_url}/", timeout=3.0)
        health["components"]["gate_controller"] = {
            "status": "healthy",
            "relay_type": settings.RELAY_TYPE,
            "url": gate_url,
        }
    except Exception:
        health["components"]["gate_controller"] = {
            "status": "simulated" if settings.RELAY_TYPE == "simulated" else "unreachable",
            "relay_type": settings.RELAY_TYPE,
            "url": settings.GATE_API_URL,
        }
        if settings.RELAY_TYPE == "http":
            issues.append("gate_controller")

    # 6. System resources
    disk = get_disk_usage(".")
    snapshot_count = count_files_in_dir(settings.SNAPSHOT_DIR)
    health["components"]["system"] = {
        "disk": disk,
        "snapshot_files": snapshot_count,
        "snapshot_retention_days": settings.SNAPSHOT_RETENTION_DAYS,
    }

    if disk.get("free_gb", 999) < 2.0:
        issues.append("disk_space")

    # 7. Redis
    try:
        from backend.utils.redis_client import redis_health
        r_health = redis_health()
        health["components"]["redis"] = r_health
        if r_health.get("status") != "healthy":
            issues.append("redis")
    except Exception as e:
        health["components"]["redis"] = {"status": "unhealthy", "error": str(e)}
        issues.append("redis")

    # 8. Database stats
    try:
        vehicles_inside = db.query(Entry).filter(Entry.status == "IN").count()
        total_vehicles = db.query(Vehicle).count()
        health["components"]["parking"] = {
            "vehicles_inside": vehicles_inside,
            "total_registered_vehicles": total_vehicles,
        }
    except Exception:
        pass

    # Overall status
    if issues:
        health["status"] = "degraded"
        health["issues"] = issues

    return health


# ---------------------------------------------------------------------------
# GET /system/metrics
# ---------------------------------------------------------------------------

@router.get("/system/metrics")
def system_metrics(db: Session = Depends(get_db)):
    """Key operational metrics for monitoring dashboards."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    vehicles_inside = db.query(Entry).filter(Entry.status == "IN").count()
    entries_today = db.query(Entry).filter(Entry.entry_time >= today_start).count()
    exits_today = db.query(Entry).filter(
        Entry.exit_time >= today_start, Entry.status == "OUT"
    ).count()
    revenue_today = db.query(func.sum(Billing.amount)).join(Entry).filter(
        Entry.exit_time >= today_start, Billing.paid == True
    ).scalar() or 0

    # Recent system alerts
    recent_alerts = db.query(SystemLog).filter(
        SystemLog.level.in_(["WARNING", "ERROR", "CRITICAL"])
    ).order_by(SystemLog.timestamp.desc()).limit(10).all()

    return {
        "timestamp": now.isoformat(),
        "uptime_seconds": round(time.time() - _app_start_time, 1),
        "vehicles_inside": vehicles_inside,
        "entries_today": entries_today,
        "exits_today": exits_today,
        "revenue_today": round(revenue_today, 2),
        "recent_alerts": [
            {
                "service": a.service_name,
                "level": a.level,
                "message": a.message,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            }
            for a in recent_alerts
        ],
    }


# ---------------------------------------------------------------------------
# GET /vehicle/{plate}
# ---------------------------------------------------------------------------

@router.get("/vehicle/{plate}")
def get_vehicle(plate: str, db: Session = Depends(get_db)):
    """Look up a vehicle by plate number. Returns registration and entry history."""
    vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail=f"Vehicle {plate} not found")

    entries = (
        db.query(Entry)
        .filter(Entry.vehicle_id == vehicle.id)
        .order_by(Entry.entry_time.desc())
        .limit(20)
        .all()
    )

    return {
        "plate_number": vehicle.plate_number,
        "registered_at": vehicle.created_at.isoformat() if vehicle.created_at else None,
        "total_visits": len(entries),
        "current_status": "INSIDE" if any(e.status == "IN" for e in entries) else "OUTSIDE",
        "history": [
            {
                "entry_id": e.id,
                "entry_time": e.entry_time.isoformat() if e.entry_time else None,
                "exit_time": e.exit_time.isoformat() if e.exit_time else None,
                "status": e.status,
                "payment_status": e.payment_status,
                "location": e.location,
                "lane": e.lane,
                "duration_minutes": round(
                    (e.exit_time - e.entry_time).total_seconds() / 60, 1
                ) if e.exit_time and e.entry_time else None,
            }
            for e in entries
        ],
    }


# ---------------------------------------------------------------------------
# GET /transactions
# ---------------------------------------------------------------------------

@router.get("/transactions")
def get_transactions(
    limit: int = Query(50, ge=1, le=500),
    status: str = Query(None, description="Filter by status: IN, OUT"),
    db: Session = Depends(get_db),
):
    """Paginated transaction history with optional status filter."""
    query = db.query(Entry).order_by(Entry.entry_time.desc())

    if status:
        query = query.filter(Entry.status == status.upper())

    entries = query.limit(limit).all()

    return [
        {
            "entry_id": e.id,
            "transaction_id": e.transaction_id or f"TXN-{e.id}",
            "plate_number": e.plate_number,
            "entry_time": e.entry_time.isoformat() if e.entry_time else None,
            "exit_time": e.exit_time.isoformat() if e.exit_time else None,
            "status": e.status,
            "payment_status": e.payment_status,
            "location": e.location,
            "lane": e.lane,
            "vehicle_type": e.vehicle_type,
            "billing": {
                "amount": e.billing.amount if e.billing else 0.0,
                "paid": e.billing.paid if e.billing else False,
                "reference": e.billing.billing_reference if e.billing else None,
            } if e.billing else None,
        }
        for e in entries
    ]
