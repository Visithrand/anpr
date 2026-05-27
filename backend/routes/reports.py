from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Any

from backend.utils.database import get_db
from backend.models.models import Entry, Vehicle

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/")
def get_reports(timeframe: str = "today", db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    now = datetime.utcnow()
    
    if timeframe == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif timeframe == "week":
        start_date = now - timedelta(days=7)
    elif timeframe == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) # Default to today
        
    entries = db.query(Entry).filter(Entry.entry_time >= start_date).order_by(Entry.entry_time.desc()).all()
    
    results = []
    for e in entries:
        stayed = "-"
        if e.exit_time:
            diff = e.exit_time - e.entry_time
            hours, remainder = divmod(diff.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            stayed = f"{int(hours)}h {int(minutes)}m"
            
        results.append({
            "transaction_id": e.transaction_id or f"TXN-{e.id}",
            "plate_number": e.plate_number,
            "entry_time": e.entry_time.isoformat() if e.entry_time else None,
            "exit_time": e.exit_time.isoformat() if e.exit_time else None,
            "stayed": stayed,
            "status": e.status,
            "location": e.location,
            "lane": e.lane,
            "vehicle_type": e.vehicle_type
        })
        
    return results
