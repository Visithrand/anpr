"""
backend/routes/gate.py
~~~~~~~~~~~~~~~~~~~~~~
Gate manual control API.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.utils.database import get_db
from backend.models.models import ManualOverride, Admin
from backend.routes.auth import get_current_admin
from backend.services.gate_service import gate_service

router = APIRouter(prefix="/api/gate", tags=["gate"])

class GateOpenRequest(BaseModel):
    reason: str = "Manual Override"

@router.post("/open")
def open_gate_manual(
    req: GateOpenRequest, 
    db: Session = Depends(get_db), 
    current_admin: Admin = Depends(get_current_admin)
):
    # Trigger gate
    gate_service.open_gate()
    
    # Log manual override
    override = ManualOverride(
        gate="EXIT", # Assuming modbus barrier is at exit for billing
        reason=f"{req.reason} (triggered by {current_admin.email})"
    )
    db.add(override)
    db.commit()
    
    return {"message": "Gate triggered successfully"}

@router.get("/status")
def get_gate_status():
    connected = gate_service.is_connected()
    return {
        "status": "connected" if connected else "disconnected",
        "host": gate_service.host,
        "port": gate_service.port
    }
