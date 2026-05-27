"""
backend/main.py
~~~~~~~~~~~~~~~~
Production ANPR.OS application entry point.

Lifespan:
  Startup:
    1. Initialize structured logging
    2. Create database tables
    3. Seed default admin
    4. Auto-start configured cameras
    5. Start watchdog health monitor

  Shutdown:
    1. Stop all camera feeds
    2. Stop watchdog
    3. Dispose database engine
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from datetime import datetime

from backend.config import settings
from backend.utils.logger import setup_logging
from backend.utils.database import engine, Base, get_db, SessionLocal
from backend.models.models import Vehicle, Entry, Billing, AuditLog
from backend.utils.websocket import manager
from backend.routes import entry, exit
from backend.routes import live as live_router
from backend.routes import reports
from backend.routes import auth as auth_router
from backend.routes import billing as billing_router
from backend.routes import health as health_router
from backend.routes.auth import seed_default_admin

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- STARTUP ----

    # 1. Structured logging
    setup_logging(
        log_dir=settings.LOG_DIR,
        log_level=settings.LOG_LEVEL,
        max_bytes=settings.LOG_MAX_BYTES,
        backup_count=settings.LOG_BACKUP_COUNT,
    )
    log.info("=" * 60)
    log.info("  ANPR.OS — Starting Up")
    log.info("=" * 60)

    # 2. Create database tables
    Base.metadata.create_all(bind=engine)
    log.info("Database tables verified/created")

    # 3. Create required directories
    os.makedirs(settings.SNAPSHOT_DIR, exist_ok=True)
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    os.makedirs("snapshots", exist_ok=True)

    # 4. Seed default admin
    db = SessionLocal()
    try:
        seed_default_admin(db)
        log.info("Default admin seeded")
    finally:
        db.close()

    # 5. Redis connection validation
    try:
        from backend.utils.redis_client import get_sync_redis
        r = get_sync_redis()
        r.ping()
        log.info("Redis connectivity verified successfully: %s", settings.REDIS_URL)
    except Exception as e:
        log.critical("Failed to connect to Redis on startup: %s. ANPR.OS requires Redis to be running.", e)
        raise RuntimeError(f"Redis is required but unreachable at {settings.REDIS_URL}") from e

    # 6. Auto-start cameras (if configured)
    if settings.CAMERA_AUTO_START and settings.camera_defaults:
        from backend.routes.live import camera_mgr
        camera_mgr.auto_start()
        log.info("Auto-started %d pre-configured cameras", len(settings.camera_defaults))

    # 7. Start watchdog
    from backend.services.watchdog import watchdog
    watchdog.start()
    log.info("Watchdog health monitor started")

    log.info("=" * 60)
    log.info("  ANPR.OS — Ready")
    log.info("=" * 60)

    yield

    # ---- SHUTDOWN ----
    log.info("ANPR.OS — Shutting down...")

    # Stop cameras
    try:
        from backend.routes.live import camera_mgr
        camera_mgr.stop_all()
        log.info("All camera feeds stopped")
    except Exception as e:
        log.error("Error stopping cameras: %s", e)

    # Stop watchdog
    try:
        from backend.services.watchdog import watchdog
        watchdog.stop()
        log.info("Watchdog stopped")
    except Exception as e:
        log.error("Error stopping watchdog: %s", e)

    # Close Redis clients
    try:
        from backend.utils.redis_client import close_async_redis
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(close_async_redis())
        else:
            asyncio.run(close_async_redis())
        log.info("Redis client closed")
    except Exception as e:
        log.error("Error closing Redis client: %s", e)

    # Dispose database engine
    try:
        engine.dispose()
        log.info("Database engine disposed")
    except Exception as e:
        log.error("Error disposing database engine: %s", e)

    log.info("ANPR.OS — Shutdown complete")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ANPR.OS",
    description="Automatic Number Plate Recognition — Parking Management System",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(entry.router)
app.include_router(exit.router)
app.include_router(live_router.router)
app.include_router(reports.router)
app.include_router(auth_router.router)
app.include_router(billing_router.router)
app.include_router(health_router.router)

# Serve plate crop images
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    return {
        "service": "ANPR.OS",
        "version": "2.0.0",
        "status": "running",
        "message": "Automatic Number Plate Recognition — Parking Management System",
    }


# ---------------------------------------------------------------------------
# Vehicle registration (simple)
# ---------------------------------------------------------------------------

@app.post("/vehicle")
def add_vehicle(plate_number: str, db: Session = Depends(get_db)):
    existing_vehicle = db.query(Vehicle).filter(
        Vehicle.plate_number == plate_number
    ).first()

    if existing_vehicle:
        raise HTTPException(status_code=400, detail="Vehicle already exists")

    vehicle = Vehicle(plate_number=plate_number)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    return {
        "message": "Vehicle added successfully",
        "vehicle_id": vehicle.id,
        "plate_number": vehicle.plate_number
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    active_records = (
        db.query(Entry.entry_time, Vehicle.plate_number)
        .join(Vehicle)
        .filter(Entry.status == "IN")
        .all()
    )

    vehicles_inside = db.query(Entry).filter(
        Entry.status == "IN"
    ).count()

    active_vehicles = [
        {
            "plate_number": r.plate_number,
            "entry_time": r.entry_time
        }
        for r in active_records
    ]

    total_revenue = db.query(func.sum(Billing.amount)).scalar() or 0

    # New metrics
    total_entries_today = db.query(Entry).filter(
        Entry.entry_time >= today_start
    ).count()

    total_exits_today = db.query(Entry).filter(
        Entry.exit_time >= today_start,
        Entry.status == "OUT"
    ).count()

    # Average stay duration (completed trips today)
    completed_today = db.query(Entry).filter(
        Entry.exit_time >= today_start,
        Entry.status == "OUT",
        Entry.exit_time.isnot(None)
    ).all()

    avg_stay = 0
    if completed_today:
        total_mins = sum(
            (e.exit_time - e.entry_time).total_seconds() / 60
            for e in completed_today
            if e.exit_time and e.entry_time
        )
        avg_stay = round(total_mins / len(completed_today), 1)

    # Recent activity (last 10 audit logs)
    recent_logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
    recent_activity = [
        {
            "action": log_entry.action,
            "plate_number": log_entry.plate_number,
            "operator": log_entry.operator,
            "timestamp": log_entry.timestamp.isoformat() if log_entry.timestamp else None,
            "details": log_entry.details,
        }
        for log_entry in recent_logs
    ]

    return {
        "vehicles_inside": vehicles_inside,
        "active_vehicles": active_vehicles,
        "total_revenue": total_revenue,
        "total_entries_today": total_entries_today,
        "total_exits_today": total_exits_today,
        "avg_stay_minutes": avg_stay,
        "recent_activity": recent_activity,
    }


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------

@app.get("/audit-logs")
def get_audit_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": log_entry.id,
            "action": log_entry.action,
            "plate_number": log_entry.plate_number,
            "operator": log_entry.operator,
            "timestamp": log_entry.timestamp,
            "details": log_entry.details
        }
        for log_entry in logs
    ]


@app.delete("/audit-logs")
def clear_audit_logs(db: Session = Depends(get_db)):
    db.query(AuditLog).delete()
    db.commit()
    return {"message": "Audit logs cleared successfully"}