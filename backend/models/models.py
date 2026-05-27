"""
backend/models/models.py
~~~~~~~~~~~~~~~~~~~~~~~~~
SQLAlchemy ORM models for the ANPR parking management system.

Tables
------
  - Vehicle        : registered vehicles (plate → entries)
  - Entry          : parking sessions (entry/exit timestamps, status, billing)
  - Billing        : payment records linked to entries
  - AuditLog       : operator / system action trail
  - Admin          : admin user accounts (JWT auth)
  - ManualOverride : manual gate overrides
  - CameraLog      : camera lifecycle events (start, stop, reconnect, error)
  - PaymentLog     : billing API request/response audit trail
  - SystemLog      : system-level events (watchdog, errors, health)
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey,
    Float, TIMESTAMP, Text, Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from backend.utils.database import Base


# ===========================================================================
# Core Domain Models
# ===========================================================================

class Vehicle(Base):
    __tablename__ = "vehicle"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    entries = relationship("Entry", back_populates="vehicle")


class Entry(Base):
    __tablename__ = "entry"

    id = Column(Integer, primary_key=True, index=True)

    transaction_id = Column(String, unique=True, index=True, nullable=True)
    plate_number = Column(String, index=True)

    vehicle_id = Column(Integer, ForeignKey("vehicle.id"))

    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)

    status = Column(String, default="IN", index=True)          # IN | OUT
    billed = Column(Boolean, default=False)

    # Payment state from third-party billing system
    payment_status = Column(String, default="PENDING")  # PENDING | PAID | REJECTED

    # Image paths saved by camera at time of capture
    vehicle_image_path = Column(String, nullable=True)
    plate_image_path = Column(String, nullable=True)

    location = Column(String, default="Main Gate")
    lane = Column(String, default="Lane 1")
    vehicle_type = Column(String, default="Unknown")

    vehicle = relationship("Vehicle", back_populates="entries")
    billing = relationship("Billing", back_populates="entry", uselist=False)

    # Composite index for the most common query: "find active entry for vehicle"
    __table_args__ = (
        Index("ix_entry_vehicle_status", "vehicle_id", "status"),
    )


class Billing(Base):
    __tablename__ = "billing"

    id = Column(Integer, primary_key=True, index=True)

    entry_id = Column(Integer, ForeignKey("entry.id"), unique=True)

    # Amount confirmed by the third-party billing system (0.0 until confirmed)
    amount = Column(Float, default=0.0, nullable=True)

    # Whether the external billing system has confirmed payment
    paid = Column(Boolean, default=False)

    # Reference ID / transaction ID returned by the external billing API
    billing_reference = Column(String, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now())

    entry = relationship("Entry", back_populates="billing")


# ===========================================================================
# Audit & Admin Models
# ===========================================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False, index=True)
    plate_number = Column(String, nullable=False, index=True)
    operator = Column(String, default="System Admin")
    timestamp = Column(TIMESTAMP, server_default=func.now())
    details = Column(String)


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, default="Admin")
    role = Column(String, default="admin")
    created_at = Column(TIMESTAMP, server_default=func.now())


class ManualOverride(Base):
    __tablename__ = "manual_overrides"

    id = Column(Integer, primary_key=True, index=True)
    gate = Column(String, nullable=False)       # 'ENTRY' or 'EXIT'
    reason = Column(String, nullable=True)       # 'Tailgating', 'System Error', etc.
    triggered_at = Column(TIMESTAMP, server_default=func.now())


# ===========================================================================
# Operational Log Models (new — for production monitoring)
# ===========================================================================

class CameraLog(Base):
    """
    Tracks camera lifecycle events for operational monitoring.
    Written by the CameraFeed class on start/stop/reconnect/error.
    """
    __tablename__ = "camera_logs"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, nullable=False, index=True)
    camera_label = Column(String, default="")
    event = Column(String, nullable=False, index=True)  # STARTED | STOPPED | RECONNECT | ERROR | FRAME_LOSS
    source = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(TIMESTAMP, server_default=func.now(), index=True)


class PaymentLog(Base):
    """
    Audit trail for every billing API call — request, response, timing.
    Critical for debugging payment failures and SAP integration issues.
    """
    __tablename__ = "payment_logs"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, nullable=False, index=True)
    api_url = Column(String, nullable=True)
    request_payload = Column(Text, nullable=True)
    response_payload = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    api_reachable = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    timestamp = Column(TIMESTAMP, server_default=func.now(), index=True)


class SystemLog(Base):
    """
    System-level events: watchdog alerts, service health, disk warnings.
    Queryable via the health/monitoring endpoints.
    """
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, nullable=False, index=True)  # watchdog, camera, billing, gate, database
    level = Column(String, nullable=False, default="INFO")     # INFO | WARNING | ERROR | CRITICAL
    message = Column(Text, nullable=False)
    traceback = Column(Text, nullable=True)
    timestamp = Column(TIMESTAMP, server_default=func.now(), index=True)