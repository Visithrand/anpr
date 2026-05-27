"""
backend/services/vehicle_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Service layer for vehicle entry creation.

Used by routes that need to programmatically create an entry record
without going through the full HTTP entry endpoint.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.models import Vehicle, Entry

log = logging.getLogger(__name__)


def get_or_create_vehicle(db: Session, plate_number: str) -> Vehicle:
    """Return existing vehicle or create a new one."""
    vehicle = db.query(Vehicle).filter(
        Vehicle.plate_number == plate_number
    ).first()

    if not vehicle:
        vehicle = Vehicle(plate_number=plate_number)
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)
        log.info("New vehicle registered: %s", plate_number)

    return vehicle


def create_entry(
    db: Session,
    plate_number: str,
    plate_image_path: Optional[str] = None,
    vehicle_image_path: Optional[str] = None,
    location: str = "Main Gate",
    lane: str = "Lane 1",
) -> Optional[Entry]:
    """
    Create an entry record for a vehicle.

    Returns None if the vehicle is already inside (duplicate prevention).
    """
    vehicle = get_or_create_vehicle(db, plate_number)

    # Duplicate check — reject if already inside
    existing = db.query(Entry).filter(
        Entry.vehicle_id == vehicle.id,
        Entry.status == "IN",
    ).first()

    if existing:
        log.warning(
            "Duplicate entry rejected: %s already inside (Entry ID: %d)",
            plate_number, existing.id,
        )
        return None

    entry = Entry(
        plate_number=plate_number,
        vehicle_id=vehicle.id,
        plate_image_path=plate_image_path,
        vehicle_image_path=vehicle_image_path,
        location=location,
        lane=lane,
        status="IN",
        payment_status="PENDING",
        billed=False,
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    log.info("Entry created: %s (ID: %d)", plate_number, entry.id)
    return entry