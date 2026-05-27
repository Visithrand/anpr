"""
backend/routes/live.py
~~~~~~~~~~~~~~~~~~~~~~
Multi-Camera Live ANPR endpoints (up to MAX_CAMERAS simultaneous cameras):
  GET  /live/cameras         → list all camera slots & status
  GET  /live/start           → start a camera feed
  GET  /live/stop            → stop a specific camera feed
  GET  /live/stop-all        → stop all camera feeds
  GET  /live/stream          → MJPEG video stream for a camera
  GET  /live/detections      → recent detections (per-camera or merged)
  DELETE /live/detections    → clear detections
  POST /live/register-entry  → register a detected plate as entry
  POST /live/approve-exit    → approve billing + open gate

Production hardening (v2):
  - Infinite RTSP reconnection with exponential backoff
  - Memory-bounded tracking structures with periodic cleanup
  - Camera lifecycle logging to CameraLog table
  - Health metadata per feed (frames processed, detections, reconnect count)
  - Configurable parameters from centralized settings
"""

import os
import uuid
import time
import threading
import logging
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, List
from difflib import SequenceMatcher
import re
import math

import cv2
import numpy as np
import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.utils.database import get_db, SessionLocal
from backend.models.models import Vehicle, Entry, Billing, AuditLog, CameraLog
from backend.services.gate_trigger import open_exit_gate, open_entry_gate
from backend.services.billing_service import check_payment_status
from backend.utils.websocket import manager
from backend.config import settings
from anpr.plate_detector import PlateDetector

log = logging.getLogger(__name__)
router = APIRouter(prefix="/live", tags=["live"])

PLATE_DIR = settings.SNAPSHOT_DIR


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def is_valid_plate(text: str) -> bool:
    clean = re.sub(r'[\s\-]', '', text).upper()
    if not re.match(r'^[A-Z0-9]{4,12}$', clean):
        return False
    has_alpha = any(c.isalpha() for c in clean)
    has_digit = any(c.isdigit() for c in clean)
    return has_alpha and has_digit


def get_iou(boxA, boxB) -> float:
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0:
        return 0.0

    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    return interArea / float(boxAArea + boxBArea - interArea)


def _log_camera_event(camera_id: int, label: str, event: str, source: str = "", details: str = ""):
    """Write a camera lifecycle event to the CameraLog table."""
    try:
        with SessionLocal() as db:
            db.add(CameraLog(
                camera_id=camera_id,
                camera_label=label,
                event=event,
                source=source,
                details=details,
            ))
            db.commit()
    except Exception as e:
        log.warning("Failed to log camera event: %s", e)


# ---------------------------------------------------------------------------
# Detection data
# ---------------------------------------------------------------------------
@dataclass
class Detection:
    plate_text: str
    confidence: float
    image_url: str
    timestamp: str
    camera_id: int = 1
    camera_label: str = "Camera 1"
    is_inside: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8].upper())
    vehicle_image_url: str = ""
    location: str = "Main Toll Plaza"
    lane: str = "Lane 1 - Entry"
    vehicle_type: str = "Unknown (Optional YOLO)"
    status: str = "OUT"
    billing_status: str = "N/A"


# ---------------------------------------------------------------------------
# CameraFeed — one independent ANPR pipeline per camera
# ---------------------------------------------------------------------------
class CameraFeed:
    """
    Each CameraFeed instance wraps a FrameCapture instance and manages:
      - Detection deque for the live UI
      - Delegation of capture start/stop to camera_service.capture.FrameCapture
    """

    def __init__(self, camera_id: int, label: str = "Camera"):
        from camera_service.capture import FrameCapture
        self.camera_id = camera_id
        self.label = label
        self.capture = FrameCapture(camera_id, label)
        self.detections: deque = deque(maxlen=100)

    @property
    def running(self) -> bool:
        return self.capture.running

    @property
    def source(self):
        return self.capture.source

    @property
    def current_frame(self) -> Optional[bytes]:
        return self.capture.current_frame

    @property
    def lock(self) -> threading.Lock:
        return self.capture.lock

    @property
    def uptime_seconds(self) -> float:
        return self.capture.uptime_seconds

    @property
    def _last_frame_time(self) -> Optional[float]:
        return self.capture._last_frame_time

    @property
    def health(self) -> dict:
        """Return health metadata for monitoring."""
        h = self.capture.health
        return {
            "camera_id": self.camera_id,
            "label": self.label,
            "running": self.running,
            "uptime_seconds": self.uptime_seconds,
            "total_frames_processed": h.get("total_frames_captured", 0),
            "total_detections": len(self.detections),
            "reconnect_count": h.get("reconnect_count", 0),
            "detection_buffer_size": len(self.detections),
            "last_frame_age_seconds": h.get("last_frame_age_seconds"),
            "source": self.source or "",
        }

    def start(self, source):
        self.detections.clear()
        self.capture.start(source)

    def stop(self):
        self.capture.stop()

    def clear_history(self):
        self.detections.clear()


# ---------------------------------------------------------------------------
# CameraManager — manages up to MAX_CAMERAS independent feeds
# ---------------------------------------------------------------------------
class CameraManager:
    """
    Production-grade camera orchestrator.
    - Thread-safe camera lifecycle management
    - Hard cap of MAX_CAMERAS simultaneous feeds
    - Merged detection queries across all cameras
    - Redis detection subscriber & auto event consumers
    """

    def __init__(self):
        self._feeds: Dict[int, CameraFeed] = {}
        self._lock = threading.Lock()
        self._pubsub_thread: Optional[threading.Thread] = None
        self._pubsub_running = False
        self._entry_thread: Optional[threading.Thread] = None
        self._exit_thread: Optional[threading.Thread] = None
        self._consumers_running = False
        self._watchdog = None
        self.last_ocr_latency = 0.0
        self.last_det_latency = 0.0
        self.last_total_latency = 0.0
        self.last_detection_time = None

    def _start_subscriber(self):
        with self._lock:
            if self._pubsub_running:
                return
            self._pubsub_running = True
            self._pubsub_thread = threading.Thread(
                target=self._subscriber_loop,
                daemon=True,
                name="DetectionSubscriber",
            )
            self._pubsub_thread.start()
            log.info("Redis detection subscriber thread started")

    def _subscriber_loop(self):
        from backend.utils.redis_client import get_sync_redis, Queues
        import json
        
        r = get_sync_redis()
        pubsub = r.pubsub()
        pubsub.subscribe(Queues.DETECTION_RESULTS)
        
        while self._pubsub_running:
            try:
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg:
                    continue
                
                data = json.loads(msg["data"].decode("utf-8"))
                self.last_ocr_latency = float(data.get("ocr_latency_ms", 0.0))
                self.last_det_latency = float(data.get("det_latency_ms", 0.0))
                self.last_total_latency = float(data.get("total_latency_ms", 0.0))
                self.last_detection_time = data.get("timestamp", datetime.utcnow().isoformat())
                
                camera_id = int(data.get("camera_id", 1))
                plate_text = data.get("plate_text", "")
                conf = float(data.get("confidence", 1.0))
                image_url = data.get("image_url", "")
                vehicle_image_url = data.get("vehicle_image_url", "")
                timestamp = data.get("timestamp", datetime.utcnow().isoformat())
                is_inside = bool(data.get("is_inside", False))
                box = data.get("box")
                
                feed = self.get_feed(camera_id)
                if feed:
                    # Update feed active annotations
                    if box:
                        feed.capture.active_annotations.append({
                            "box": box,
                            "plate_text": plate_text,
                            "confidence": conf,
                            "timestamp": time.time(),
                        })
                    
                    # Update detections list (same merging/dedup logic)
                    existing_det = None
                    for d in feed.detections:
                        try:
                            det_time = datetime.fromisoformat(d.timestamp)
                            if (datetime.utcnow() - det_time).total_seconds() < 300:
                                if (similar(d.plate_text, plate_text) > 0.65
                                        or plate_text in d.plate_text
                                        or d.plate_text in plate_text):
                                    existing_det = d
                                    break
                        except (ValueError, TypeError):
                            continue
                            
                    if existing_det:
                        if len(plate_text) > len(existing_det.plate_text):
                            existing_det.plate_text = plate_text
                        existing_det.timestamp = datetime.utcnow().isoformat()
                        existing_det.confidence = max(existing_det.confidence, round(conf, 3))
                        existing_det.image_url = image_url
                        existing_det.vehicle_image_url = vehicle_image_url
                        existing_det.is_inside = is_inside
                        existing_det.status = "IN" if is_inside else "OUT"
                        existing_det.billing_status = "Pending" if is_inside else "Paid / N/A"
                        # Move to front
                        feed.detections.remove(existing_det)
                        feed.detections.appendleft(existing_det)
                    else:
                        det = Detection(
                            plate_text=plate_text,
                            confidence=round(conf, 3),
                            image_url=image_url,
                            vehicle_image_url=vehicle_image_url,
                            timestamp=timestamp,
                            camera_id=camera_id,
                            camera_label=feed.label,
                            is_inside=is_inside,
                            status="IN" if is_inside else "OUT",
                            billing_status="Pending" if is_inside else "Paid / N/A"
                        )
                        feed.detections.appendleft(det)
                        
            except Exception as e:
                log.error("Error in detection subscriber thread: %s", e)
                time.sleep(0.1)

    def _start_watchdog(self):
        with self._lock:
            if self._watchdog:
                return
            from camera_service.watchdog import CameraWatchdog
            self._watchdog = CameraWatchdog(self, interval=settings.WATCHDOG_INTERVAL_SECONDS)
            self._watchdog.start()

    def _start_event_consumers(self):
        with self._lock:
            if self._consumers_running:
                return
            self._consumers_running = True
            
            self._entry_thread = threading.Thread(
                target=self._entry_events_loop,
                daemon=True,
                name="EntryEventsConsumer",
            )
            self._entry_thread.start()
            
            self._exit_thread = threading.Thread(
                target=self._exit_events_loop,
                daemon=True,
                name="ExitEventsConsumer",
            )
            self._exit_thread.start()
            log.info("Redis event consumer threads started")

    def _entry_events_loop(self):
        from backend.utils.redis_client import get_sync_redis, Queues
        import json
        
        r = get_sync_redis()
        while self._consumers_running:
            try:
                event_data = r.brpop(Queues.ENTRY_EVENTS, timeout=1.0)
                if not event_data:
                    continue
                
                _, payload_bytes = event_data
                payload = json.loads(payload_bytes.decode("utf-8"))
                plate_number = payload.get("plate_number")
                image_url = payload.get("image_url", "")
                vehicle_image_url = payload.get("vehicle_image_url", "")
                
                if not plate_number:
                    continue
                    
                log.info("Auto-processing Entry Event for: %s", plate_number)
                
                with SessionLocal() as db:
                    vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate_number).first()
                    if not vehicle:
                        vehicle = Vehicle(plate_number=plate_number)
                        db.add(vehicle)
                        db.commit()
                        db.refresh(vehicle)
                        
                    existing_entry = db.query(Entry).filter(
                        Entry.vehicle_id == vehicle.id,
                        Entry.status == "IN"
                    ).first()
                    
                    if existing_entry:
                        log.warning("Vehicle %s is already registered as inside, skipping auto-entry.", plate_number)
                        continue
                        
                    entry = Entry(
                        plate_number=plate_number,
                        vehicle_id=vehicle.id,
                        entry_time=datetime.utcnow(),
                        status="IN",
                        payment_status="PENDING",
                        plate_image_path=image_url,
                        vehicle_image_path=vehicle_image_url,
                        location="Main Gate",
                        lane="Lane 1 - Entry",
                    )
                    db.add(entry)
                    db.flush()
                    
                    billing = Billing(entry_id=entry.id, amount=0.0, paid=False)
                    db.add(billing)
                    
                    db.add(AuditLog(
                        action="ENTRY",
                        plate_number=plate_number,
                        operator="ANPR-Auto",
                        details=f"Auto vehicle entry registered at Main Gate. Awaiting billing.",
                    ))
                    db.commit()
                    
                import asyncio
                try:
                    asyncio.run(open_entry_gate())
                    asyncio.run(manager.broadcast('{"type": "REFRESH_DASHBOARD"}'))
                except Exception as loop_err:
                    log.error("Failed to run entry gate trigger: %s", loop_err)
                    
            except Exception as e:
                log.error("Error in entry events loop: %s", e)
                time.sleep(0.1)

    def _exit_events_loop(self):
        from backend.utils.redis_client import get_sync_redis, Queues
        import json
        
        r = get_sync_redis()
        while self._consumers_running:
            try:
                event_data = r.brpop(Queues.EXIT_EVENTS, timeout=1.0)
                if not event_data:
                    continue
                
                _, payload_bytes = event_data
                payload = json.loads(payload_bytes.decode("utf-8"))
                plate_number = payload.get("plate_number")
                
                if not plate_number:
                    continue
                    
                log.info("Auto-processing Exit Event for: %s", plate_number)
                
                with SessionLocal() as db:
                    vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate_number).first()
                    if not vehicle:
                        log.warning("Exit failed: Vehicle %s not in DB", plate_number)
                        continue
                        
                    entry = db.query(Entry).filter(
                        Entry.vehicle_id == vehicle.id,
                        Entry.status == "IN"
                    ).first()
                    
                    if not entry:
                        log.warning("Exit failed: No active entry for vehicle %s", plate_number)
                        continue
                        
                import asyncio
                async def process_exit():
                    from backend.services.billing_service import check_payment_status
                    payment = await check_payment_status(plate_number)
                    
                    with SessionLocal() as db:
                        db_vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate_number).first()
                        db_entry = db.query(Entry).filter(
                            Entry.vehicle_id == db_vehicle.id,
                            Entry.status == "IN"
                        ).first()
                        
                        if not payment["paid"]:
                            db.add(AuditLog(
                                action="EXIT_DENIED",
                                plate_number=plate_number,
                                operator="ANPR-Auto",
                                details=f"Auto exit denied — payment not confirmed: {payment['message']}",
                            ))
                            db.commit()
                            await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')
                            log.warning("Auto-exit denied for %s — payment pending.", plate_number)
                            return
                            
                        exit_time = datetime.utcnow()
                        duration_min = round((exit_time - db_entry.entry_time).total_seconds() / 60, 1)
                        
                        db_entry.exit_time = exit_time
                        db_entry.status = "OUT"
                        db_entry.billed = True
                        db_entry.payment_status = "PAID"
                        
                        billing = db_entry.billing
                        if billing:
                            billing.paid = True
                            billing.amount = payment["amount"]
                            billing.billing_reference = payment["reference"]
                        else:
                            billing = Billing(
                                entry_id=db_entry.id,
                                amount=payment["amount"],
                                paid=True,
                                billing_reference=payment["reference"],
                            )
                            db.add(billing)
                            
                        db.add(AuditLog(
                            action="EXIT_APPROVED",
                            plate_number=plate_number,
                            operator="ANPR-Auto",
                            details=f"Auto exit approved. Duration: {duration_min} min. Amount: {payment['amount']}.",
                        ))
                        db.commit()
                        
                    await open_exit_gate()
                    await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')
                    log.info("Auto-exit approved and gate opened for %s", plate_number)
                    
                try:
                    asyncio.run(process_exit())
                except Exception as loop_err:
                    log.error("Failed to process auto-exit: %s", loop_err)
                    
            except Exception as e:
                log.error("Error in exit events loop: %s", e)
                time.sleep(0.1)

    def start_camera(self, camera_id: int, source, label: str = "Camera") -> CameraFeed:
        if camera_id < 1 or camera_id > settings.MAX_CAMERAS:
            raise ValueError(f"camera_id must be between 1 and {settings.MAX_CAMERAS}")

        self._start_subscriber()
        self._start_event_consumers()
        self._start_watchdog()

        with self._lock:
            if camera_id in self._feeds and self._feeds[camera_id].running:
                self._feeds[camera_id].stop()

            feed = CameraFeed(camera_id=camera_id, label=label)
            feed.start(source)
            self._feeds[camera_id] = feed
            return feed

    def stop_camera(self, camera_id: int):
        with self._lock:
            if camera_id in self._feeds:
                self._feeds[camera_id].stop()

    def stop_all(self):
        with self._lock:
            for feed in self._feeds.values():
                if feed.running:
                    feed.stop()
            self._pubsub_running = False
            self._consumers_running = False
            if self._watchdog:
                self._watchdog.stop()
                self._watchdog = None

    def get_feed(self, camera_id: int) -> Optional[CameraFeed]:
        return self._feeds.get(camera_id)

    def list_cameras(self) -> List[dict]:
        result = []
        for cam_id in range(1, settings.MAX_CAMERAS + 1):
            feed = self._feeds.get(cam_id)
            if feed:
                result.append({
                    "id": cam_id,
                    "label": feed.label,
                    "source": str(feed.source) if feed.source else "",
                    "running": feed.running,
                    "uptime": feed.uptime_seconds,
                    "detection_count": len(feed.detections),
                })
            else:
                result.append({
                    "id": cam_id,
                    "label": f"Camera {cam_id}",
                    "source": "",
                    "running": False,
                    "uptime": 0,
                    "detection_count": 0,
                })
        return result

    def get_all_detections(self, limit: int = 50) -> List[dict]:
        """Merge detections from all active cameras, sorted newest first."""
        all_dets = []
        for feed in self._feeds.values():
            all_dets.extend(list(feed.detections))
        all_dets.sort(key=lambda d: d.timestamp, reverse=True)
        return [asdict(d) for d in all_dets[:limit]]

    def get_camera_detections(self, camera_id: int, limit: int = 50) -> List[dict]:
        feed = self._feeds.get(camera_id)
        if not feed:
            return []
        items = list(feed.detections)[:limit]
        return [asdict(d) for d in items]

    def clear_detections(self, camera_id: Optional[int] = None):
        if camera_id:
            feed = self._feeds.get(camera_id)
            if feed:
                feed.clear_history()
        else:
            for feed in self._feeds.values():
                feed.clear_history()

    def auto_start(self):
        """Start cameras pre-configured in .env (called during app startup)."""
        self._start_subscriber()
        self._start_event_consumers()
        for cam_id, cam_cfg in settings.camera_defaults.items():
            source = cam_cfg["source"]
            label = cam_cfg["label"]
            src = int(source) if source.isdigit() else source
            try:
                self.start_camera(cam_id, src, label)
                log.info("Auto-started camera %d: source=%s, label=%s", cam_id, source, label)
            except Exception as e:
                log.error("Failed to auto-start camera %d: %s", cam_id, e)

    def health_report(self) -> List[dict]:
        """Return per-camera health data for the health endpoint."""
        reports = []
        for cam_id in range(1, settings.MAX_CAMERAS + 1):
            feed = self._feeds.get(cam_id)
            if feed:
                reports.append(feed.health)
            else:
                reports.append({
                    "camera_id": cam_id,
                    "label": f"Camera {cam_id}",
                    "running": False,
                    "uptime_seconds": 0,
                    "total_frames_processed": 0,
                    "total_detections": 0,
                    "reconnect_count": 0,
                    "detection_buffer_size": 0,
                    "last_frame_age_seconds": None,
                    "source": "",
                })
        return reports

    @property
    def active_count(self) -> int:
        return sum(1 for f in self._feeds.values() if f.running)

    def get_monitoring_metrics(self) -> dict:
        from backend.utils.redis_client import redis_health
        r_health = redis_health()
        return {
            "active_cameras": self.active_count,
            "queue_size": r_health.get("queues", {}).get("ocr_queue", 0),
            "last_ocr_latency": self.last_ocr_latency,
            "last_det_latency": self.last_det_latency,
            "last_total_latency": self.last_total_latency,
            "last_detection_time": self.last_detection_time,
        }


# Singleton instance
camera_mgr = CameraManager()


# ---------------------------------------------------------------------------
# MJPEG generator (per camera)
# ---------------------------------------------------------------------------
def _mjpeg_gen(camera_id: int):
    feed = camera_mgr.get_feed(camera_id)
    if not feed:
        return

    while feed.running:
        with feed.lock:
            frame = feed.current_frame
        if frame is None:
            time.sleep(0.05)
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )
        time.sleep(0.033)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/monitoring-metrics")
def get_monitoring_metrics():
    """Return metrics for the monitoring dashboard."""
    return camera_mgr.get_monitoring_metrics()


@router.get("/cameras")
def list_cameras():
    """List all camera slots (1–MAX_CAMERAS) with their current status."""
    return camera_mgr.list_cameras()


@router.get("/start")
def start_feed(
    source: str = Query("sample.mp4"),
    camera_id: int = Query(1, ge=1, le=settings.MAX_CAMERAS),
    label: str = Query("Camera 1"),
):
    """Start a specific camera feed. Defaults to camera 1 for backward compatibility."""
    src = int(source) if source.isdigit() else source
    try:
        camera_mgr.start_camera(camera_id, src, label)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "started", "camera_id": camera_id, "source": source, "label": label}


@router.get("/stop")
def stop_feed(camera_id: int = Query(1, ge=1, le=settings.MAX_CAMERAS)):
    """Stop a specific camera feed."""
    camera_mgr.stop_camera(camera_id)
    return {"status": "stopped", "camera_id": camera_id}


@router.get("/stop-all")
def stop_all_feeds():
    """Stop all active camera feeds."""
    camera_mgr.stop_all()
    return {"status": "all_stopped"}


@router.get("/stream")
def mjpeg_stream(camera_id: int = Query(1, ge=1, le=settings.MAX_CAMERAS)):
    """MJPEG video stream for a specific camera."""
    feed = camera_mgr.get_feed(camera_id)
    if not feed or not feed.running:
        raise HTTPException(400, f"Camera {camera_id} is not running. Start it first.")
    return StreamingResponse(
        _mjpeg_gen(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/detections")
def get_detections(
    limit: int = 50,
    camera_id: Optional[int] = Query(None, ge=1, le=settings.MAX_CAMERAS),
):
    """
    Get recent detections.
    - If camera_id is specified, returns detections from that camera only.
    - If omitted, returns merged detections from all cameras.
    """
    if camera_id:
        return camera_mgr.get_camera_detections(camera_id, limit)
    return camera_mgr.get_all_detections(limit)


@router.delete("/detections")
def clear_detections(
    camera_id: Optional[int] = Query(None, ge=1, le=settings.MAX_CAMERAS),
):
    """Clear detections. If camera_id specified, clears only that camera."""
    camera_mgr.clear_detections(camera_id)
    return {"status": "cleared", "camera_id": camera_id or "all"}


@router.post("/register-entry")
async def register_entry(
    plate_number: str,
    plate_image_url: str = "",
    vehicle_image_url: str = "",
    operator: str = "Live-Operator",
    db: Session = Depends(get_db),
):
    """
    Register a detected plate as a vehicle entry.
    Called from the Live Dashboard when operator clicks 'Register Entry'.
    Entry boom barrier is opened immediately.
    """
    vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate_number).first()
    if not vehicle:
        vehicle = Vehicle(plate_number=plate_number)
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)

    existing = db.query(Entry).filter(Entry.vehicle_id == vehicle.id, Entry.status == "IN").first()
    if existing:
        raise HTTPException(400, f"Vehicle {plate_number} is already inside (Entry ID: {existing.id})")

    entry = Entry(
        plate_number=plate_number,
        vehicle_id=vehicle.id,
        entry_time=datetime.utcnow(),
        status="IN",
        payment_status="PENDING",
        plate_image_path=plate_image_url,
        vehicle_image_path=vehicle_image_url,
    )
    db.add(entry)
    db.flush()

    # Create pending billing record
    billing = Billing(entry_id=entry.id, amount=0.0, paid=False)
    db.add(billing)

    db.add(AuditLog(
        action="ENTRY",
        plate_number=plate_number,
        operator=operator,
        details=f"Live entry registered: {plate_number}. Awaiting billing confirmation.",
    ))
    db.commit()

    gate = await open_entry_gate()
    await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')

    return {
        "message": "Entry registered — entry gate opened",
        "plate_number": plate_number,
        "status": "IN",
        "payment_status": "PENDING",
        "gate": gate,
    }


@router.post("/approve-exit")
async def approve_exit(
    plate_number: str,
    operator: str = "Live-Operator",
    db: Session = Depends(get_db),
):
    """
    Process exit for a detected plate.
    Queries external billing API — gate only opens if payment is confirmed.
    Called from the Live Dashboard when operator clicks 'Process Exit'.
    """
    vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate_number).first()
    if not vehicle:
        raise HTTPException(404, "Vehicle not found")

    entry = db.query(Entry).filter(Entry.vehicle_id == vehicle.id, Entry.status == "IN").first()
    if not entry:
        raise HTTPException(400, "No active entry for this vehicle")

    # Check if already marked as PAID locally, otherwise query external Billing API
    if entry.payment_status == "PAID" or (entry.billing and entry.billing.paid):
        payment = {
            "paid": True,
            "amount": entry.billing.amount if entry.billing else 0.0,
            "reference": entry.billing.billing_reference if entry.billing else "LOCAL",
            "message": "Payment verified locally via database status",
            "api_reachable": True
        }
    else:
        payment = await check_payment_status(plate_number)

    if not payment["paid"]:
        # Payment not confirmed — gate stays closed
        db.add(AuditLog(
            action="EXIT_DENIED",
            plate_number=plate_number,
            operator=operator,
            details=(
                f"Exit denied — payment not confirmed. "
                f"Billing API reachable: {payment['api_reachable']}. "
                f"Reason: {payment['message']}"
            ),
        ))
        db.commit()
        await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')

        raise HTTPException(
            status_code=402,
            detail={
                "message": "Exit denied — payment not yet confirmed by billing system",
                "plate_number": plate_number,
                "payment_status": "PENDING",
                "gate": "closed",
                "reason": payment["message"],
                "api_reachable": payment["api_reachable"],
            },
        )

    # Payment confirmed — process exit
    exit_time = datetime.utcnow()
    duration_min = round((exit_time - entry.entry_time).total_seconds() / 60, 1)

    entry.exit_time = exit_time
    entry.status = "OUT"
    entry.billed = True
    entry.payment_status = "PAID"

    # Update billing record
    billing = entry.billing
    if billing:
        billing.paid = True
        billing.amount = payment["amount"]
        billing.billing_reference = payment["reference"]
    else:
        billing = Billing(
            entry_id=entry.id,
            amount=payment["amount"],
            paid=True,
            billing_reference=payment["reference"],
        )
        db.add(billing)

    db.add(AuditLog(
        action="EXIT_APPROVED",
        plate_number=plate_number,
        operator=operator,
        details=(
            f"Exit approved. Duration: {duration_min} min. "
            f"Amount: {payment['amount']}. "
            f"Ref: {payment['reference']}. "
            f"{payment['message']}"
        ),
    ))
    db.commit()

    gate = await open_exit_gate()
    await manager.broadcast('{"type": "REFRESH_DASHBOARD"}')

    return {
        "message": "Payment confirmed — exit gate opened",
        "plate_number": plate_number,
        "duration_minutes": duration_min,
        "amount": payment["amount"],
        "billing_reference": payment["reference"],
        "billing_notes": payment["message"],
        "status": "OUT",
        "payment_status": "PAID",
        "gate": gate,
    }