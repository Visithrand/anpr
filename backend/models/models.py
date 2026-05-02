from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.utils.database import Base

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    entries = relationship("Entry", back_populates="vehicle")


class Entry(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String, unique=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    entry_time = Column(TIMESTAMP, server_default=func.now())
    exit_time = Column(TIMESTAMP)
    status = Column(String, default="IN", index=True)

    vehicle = relationship("Vehicle", back_populates="entries")
    billing = relationship("Billing", back_populates="entry", uselist=False)


class Billing(Base):
    __tablename__ = "billing"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("entries.id"))
    duration_minutes = Column(Float)
    amount = Column(Float)
    paid = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    entry = relationship("Entry", back_populates="billing")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False, index=True)
    plate_number = Column(String, nullable=False, index=True)
    operator = Column(String, default="System Admin")
    timestamp = Column(TIMESTAMP, server_default=func.now())
    details = Column(String)