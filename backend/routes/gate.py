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
    gate_type: str = "entry"  # "entry" or "exit"

@router.post("/open")
def open_gate_manual(
    req: GateOpenRequest, 
    db: Session = Depends(get_db), 
    current_admin: Admin = Depends(get_current_admin)
):
    # Trigger gate with the specified type (entry=coil 512, exit=coil 513)
    gate_service.open_gate(gate_type=req.gate_type)
    
    # Log manual override
    override = ManualOverride(
        gate=req.gate_type.upper(),
        reason=f"{req.reason} (triggered by {current_admin.email})"
    )
    db.add(override)
    db.commit()
    
    return {"message": f"{req.gate_type.capitalize()} gate triggered successfully"}

@router.get("/status")
def get_gate_status():
    connected = gate_service.is_connected()
    return {
        "status": "connected" if connected else "disconnected",
        "host": gate_service.host,
        "port": gate_service.port
    }
