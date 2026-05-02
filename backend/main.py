from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.sql import func
from sqlalchemy.orm import Session

from backend.utils.database import engine, Base, get_db
from backend.models.models import Vehicle, Entry, Billing, AuditLog
from backend.utils.websocket import manager
from backend.routes import entry, exit


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(entry.router)
app.include_router(exit.router)


@app.get("/")
def read_root():
    return {"message": "DB Connected Successfully 🚀"}


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


@app.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
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

    return {
        "vehicles_inside": vehicles_inside,
        "active_vehicles": active_vehicles,
        "total_revenue": total_revenue
    }


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/audit-logs")
def get_audit_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": log.id,
            "action": log.action,
            "plate_number": log.plate_number,
            "operator": log.operator,
            "timestamp": log.timestamp,
            "details": log.details
        }
        for log in logs
    ]