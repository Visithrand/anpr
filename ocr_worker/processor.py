"""
ocr_worker/processor.py
~~~~~~~~~~~~~~~~~~~~~~~~
Main worker processor that decodes camera frames, runs detection/OCR,
handles deduplication/cooldown, and pushes results and entry/exit events.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import uuid
from typing import Dict, List, Tuple

import cv2
import numpy as np

from backend.config import settings
from backend.models.models import Entry, Vehicle
from backend.utils.database import SessionLocal
from backend.utils.helpers import normalize_plate
from backend.utils.redis_client import (
    Queues,
    check_and_set_cooldown,
    get_sync_redis,
    publish_detection,
)
from ocr_worker.detector import DetectorWrapper
from ocr_worker.ocr_engine import OCREngine, is_valid_plate

log = logging.getLogger(__name__)


def get_iou(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """Calculate intersection over union of two bounding boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(max(0, yB - yA), 0)
    if interArea == 0:
        return 0.0

    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    return interArea / float(boxAArea + boxBArea - interArea)


def _apply_nms(boxes: List[Tuple[int, int, int, int, float]], iou_threshold: float = 0.3) -> List[Tuple[int, int, int, int, float]]:
    """
    Non-Maximum Suppression with containment filtering.

    Removes overlapping or nested bounding boxes to prevent duplicate
    OCR reads from two-line plates (e.g. top-half 'DL7S' + bottom-half 'CB4578'
    nested inside the full plate 'DL7SCB4578').

    Uses both standard IoU and Intersection-over-Minimum (IoM) to catch
    boxes that are fully contained inside a larger box.
    """
    if len(boxes) <= 1:
        return boxes

    # Sort by area descending (prefer larger, more complete plate boxes)
    sorted_boxes = sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    keep: List[Tuple[int, int, int, int, float]] = []

    for candidate in sorted_boxes:
        cx1, cy1, cx2, cy2, cconf = candidate
        suppressed = False

        for kept in keep:
            kx1, ky1, kx2, ky2, _ = kept

            # Calculate intersection
            ix1 = max(cx1, kx1)
            iy1 = max(cy1, ky1)
            ix2 = min(cx2, kx2)
            iy2 = min(cy2, ky2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)

            if inter == 0:
                continue

            area_c = max(1, (cx2 - cx1) * (cy2 - cy1))
            area_k = max(1, (kx2 - kx1) * (ky2 - ky1))
            union = area_c + area_k - inter

            iou = inter / union if union > 0 else 0
            # IoM: how much of the smaller box is inside the bigger one
            iom = inter / min(area_c, area_k)

            if iou > iou_threshold or iom > 0.6:
                suppressed = True
                break

        if not suppressed:
            keep.append(candidate)

    return keep


def _select_best_box(boxes: List[Tuple[int, int, int, int, float]]) -> Tuple[int, int, int, int, float]:
    """
    Select the single best bounding box from a list.
    
    Prefers the box with the largest area (most complete plate crop).
    Among boxes with similar area (within 20%), picks the one with highest confidence.
    """
    if len(boxes) == 1:
        return boxes[0]
    
    # Score = area * confidence_boost
    # This favors larger boxes (full plates) over smaller partial crops
    def score(box):
        x1, y1, x2, y2, conf = box
        area = (x2 - x1) * (y2 - y1)
        return area * (0.5 + conf)  # Area weighted by confidence
    
    return max(boxes, key=score)


class OCRProcessor:
    """
    Processor orchestrator for the OCR Worker.
    Consumes frames from the Redis queue, runs the OCR pipeline,
    and publishes results/events.
    """

    def __init__(self):
        self.detector = DetectorWrapper()
        self.ocr_engine = OCREngine()
        self.redis = get_sync_redis()
        self.running = False

        # Spatial dedup tracking: camera_id -> list of (box, plate_text, timestamp)
        self._recent_ocr_boxes: Dict[int, List[Tuple[Tuple[int, int, int, int], str, float]]] = {}
        
        # Plate-level dedup: tracks the last time each plate text was published
        # per camera. This is an in-memory complement to the Redis cooldown.
        self._published_plates: Dict[str, float] = {}

    def start(self):
        self.running = True
        log.info("OCRProcessor initialized and running.")
        self._loop()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                # BRPOP is blocking; wait up to 1 second for a task
                task_data = self.redis.brpop(Queues.OCR, timeout=1)
                if not task_data:
                    continue

                # brpop returns a tuple: (queue_name, value)
                _, payload_bytes = task_data
                payload = json.loads(payload_bytes.decode("utf-8"))

                self._process_task(payload)

            except Exception as e:
                log.error("Error in OCRProcessor loop: %s", e, exc_info=True)
                time.sleep(0.1)

    def _is_plate_recently_published(self, plate_text: str, cooldown: float = None) -> bool:
        """
        Check if this plate was recently published (in-memory check).
        
        This is faster than the Redis cooldown check and prevents the same plate
        from being published multiple times within a short window even if
        the Redis cooldown hasn't been set yet.
        """
        if cooldown is None:
            cooldown = float(settings.PLATE_COOLDOWN_SECONDS)
        
        last_published = self._published_plates.get(plate_text)
        if last_published and (time.time() - last_published) < cooldown:
            return True
        return False

    def _mark_plate_published(self, plate_text: str):
        """Record that this plate was just published."""
        self._published_plates[plate_text] = time.time()
        
        # Cleanup old entries (older than 5 minutes)
        now = time.time()
        stale_keys = [k for k, v in self._published_plates.items() if now - v > 300]
        for k in stale_keys:
            del self._published_plates[k]

    def _process_task(self, payload: dict):
        camera_id = payload.get("camera_id", 1)
        camera_label = payload.get("camera_label", "Camera")
        frame_b64 = payload.get("frame_b64")
        timestamp = payload.get("timestamp", time.time())

        if not frame_b64:
            return

        # 1. Decode frame from base64
        try:
            img_bytes = base64.b64decode(frame_b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            log.error("Failed to decode frame from base64 (camera %d): %s", camera_id, e)
            return

        if frame is None or frame.size == 0:
            return

        # Initialize spatial box memory for this camera if not exists
        if camera_id not in self._recent_ocr_boxes:
            self._recent_ocr_boxes[camera_id] = []

        # Clean old spatial tracking boxes (older than cooldown period)
        now = time.time()
        spatial_window = float(settings.PLATE_COOLDOWN_SECONDS)
        self._recent_ocr_boxes[camera_id] = [
            b for b in self._recent_ocr_boxes[camera_id] if now - b[2] < spatial_window
        ]

        # 2. Run plate detection
        det_start = time.time()
        raw_boxes = self.detector.detect_plates(frame)
        det_latency = time.time() - det_start
        if not raw_boxes:
            return

        # 2b. Apply NMS to suppress nested / overlapping half-plate boxes
        nms_boxes = _apply_nms(raw_boxes, iou_threshold=0.3)
        
        # 2c. Select the single best box — process only ONE plate per frame
        # This prevents the same plate from being read multiple times with
        # slightly different crops
        if not nms_boxes:
            return
        
        # Filter by confidence first
        confident_boxes = [b for b in nms_boxes if b[4] >= settings.PLATE_CONFIDENCE_THRESHOLD]
        if not confident_boxes:
            return
        
        best_box = _select_best_box(confident_boxes)
        x1, y1, x2, y2, conf = best_box

        # 3. Spatial overlap check — SKIP ENTIRELY if this box matches a recent detection
        current_box_coords = (x1, y1, x2, y2)
        for tracked_box, tracked_text, tracked_time in self._recent_ocr_boxes[camera_id]:
            iou = get_iou(current_box_coords, tracked_box)
            if iou > 0.5:
                # This plate location was already processed — skip completely
                log.debug("Spatial dedup: box overlaps with tracked plate %s (IoU=%.2f), skipping.",
                         tracked_text, iou)
                return  # <-- RETURN, not continue. Don't publish again.

        # 4. Crop plate ONCE and reuse for both OCR and snapshot saving
        crop = self.detector.crop_plate(frame, best_box, margin=10)
        
        if crop is None or crop.size == 0:
            return

        # 5. Run OCR (consensus reads)
        ocr_start = time.time()
        raw_text = self.ocr_engine.read_plate(crop)
        ocr_latency = time.time() - ocr_start
        
        if not raw_text or not is_valid_plate(raw_text):
            return
        
        plate_text = normalize_plate(raw_text)
        
        if not plate_text:
            return

        # 6. Record this box+text in spatial tracking
        self._recent_ocr_boxes[camera_id].append((current_box_coords, plate_text, now))

        # 7. In-memory dedup check (fast path)
        if self._is_plate_recently_published(plate_text):
            log.debug("Plate %s from camera %d is in local cooldown, skipping.", plate_text, camera_id)
            return

        # 8. Redis cooldown check (distributed dedup)
        is_new_detection = check_and_set_cooldown(plate_text, settings.PLATE_COOLDOWN_SECONDS)
        if not is_new_detection:
            log.debug("Plate %s from camera %d is in Redis cooldown, skipping.", plate_text, camera_id)
            return

        # Mark as published in local memory too
        self._mark_plate_published(plate_text)

        # 9. Save snapshots (reuse the crop from step 4)
        fname = f"{plate_text}_{uuid.uuid4().hex[:6]}.jpg"
        fpath = os.path.join(settings.SNAPSHOT_DIR, fname)
        cv2.imwrite(fpath, crop)

        full_fname = f"full_{plate_text}_{uuid.uuid4().hex[:6]}.jpg"
        full_fpath = os.path.join(settings.SNAPSHOT_DIR, full_fname)
        cv2.imwrite(full_fpath, frame)

        # 10. Check DB for vehicle status (IN / OUT)
        is_inside = False
        try:
            with SessionLocal() as db:
                entry_rec = db.query(Entry).join(Vehicle).filter(
                    Vehicle.plate_number == plate_text,
                    Entry.status == "IN"
                ).first()
                is_inside = entry_rec is not None
        except Exception as db_err:
            log.warning("OCR Worker database check failed for %s: %s", plate_text, db_err)

        # 11. Create detection object payload
        detection_payload = {
            "plate_text": plate_text,
            "confidence": round(conf, 3),
            "image_url": f"/static/plates/{fname}",
            "vehicle_image_url": f"/static/plates/{full_fname}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp)),
            "camera_id": camera_id,
            "camera_label": camera_label,
            "is_inside": is_inside,
            "status": "IN" if is_inside else "OUT",
            "billing_status": "Pending" if is_inside else "Paid / N/A",
            "box": [int(x1), int(y1), int(x2), int(y2)],
            "ocr_latency_ms": round(ocr_latency * 1000, 1),
            "det_latency_ms": round(det_latency * 1000, 1),
            "total_latency_ms": round((time.time() - timestamp) * 1000, 1),
        }

        # 12. Publish detection result to the pub/sub channel for frontend overlay
        publish_detection(detection_payload)
        log.info("Published detection: %s (OCR: %.1fms, Total: %.1fms) from camera %d", 
                 plate_text, ocr_latency * 1000, (time.time() - timestamp) * 1000, camera_id)

        # 13. Push to entry / exit queues for automatic gate / logic handling
        # In our system: Camera 1 = Entry Gate, Camera 2 = Exit Gate (by default)
        event_payload = json.dumps({
            "plate_number": plate_text,
            "camera_id": camera_id,
            "timestamp": timestamp,
            "image_url": f"/static/plates/{fname}",
            "vehicle_image_url": f"/static/plates/{full_fname}",
        })

        if camera_id == 1:
            # Entry Camera
            self.redis.lpush(Queues.ENTRY_EVENTS, event_payload)
            log.info("Pushed entry event to Redis: %s", plate_text)
        elif camera_id == 2:
            # Exit Camera
            self.redis.lpush(Queues.EXIT_EVENTS, event_payload)
            log.info("Pushed exit event to Redis: %s", plate_text)
