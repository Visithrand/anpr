from sqlalchemy import Column, Integer, String, TIMESTAMP
from sqlalchemy.sql import func
from backend.utils.database import Base

class ManualOverride(Base):
    __tablename__ = "manual_overrides"

    id = Column(Integer, primary_key=True, index=True)
    gate = Column(String, nullable=False)  # e.g., 'ENTRY' or 'EXIT'
    reason = Column(String, nullable=True) # e.g., 'Tailgating', 'System Error'
    triggered_at = Column(TIMESTAMP, server_default=func.now())
