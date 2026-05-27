"""
camera_service/capture.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure frame capture — NO plate detection, NO OCR.

Each FrameCapture instance:
  1. Opens an RTSP / file / webcam source
  2. Reads frames at controlled FPS
  3. Publishes every Nth frame to Redis ``ocr_queue`` as base64 JPEG
  4. Maintains a JPEG frame buffer for MJPEG live streaming
  5. Reconnects infinitely on stream loss (exponential backoff)

The capture thread NEVER runs OpenVINO or calls the OCR service.
Those responsibilities belong to the OCR Worker.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from typing import Dict, Optional

import cv2

from backend.config import settings
from backend.utils.redis_client import push_ocr_task, Queues, get_sync_redis
from camera_service.reconnect import ReconnectManager

log = logging.getLogger(__name__)


class FrameCapture:
    """
    Lightweight camera capture thread.

    Responsibilities:
      ✅ Open RTSP / file / webcam source
      ✅ Read frames with FPS throttling
      ✅ Publish frames to Redis OCR queue
      ✅ Update MJPEG frame buffer
      ✅ Reconnect infinitely on failure
      ✅ Health metrics

    NOT responsible for:
      ❌ Plate detection (OpenVINO)
      ❌ OCR calls
      ❌ Detection dedup / cooldown
      ❌ Snapshot saving
      ❌ DB lookups
    """

    def __init__(self, camera_id: int, label: str = "Camera"):
        self.camera_id = camera_id
        self.label = label
        self.source = None
        self.running = False

        # MJPEG frame buffer
        self.current_frame: Optional[bytes] = None
        self.active_annotations: list = []  # List of dicts: {"box": [x1,y1,x2,y2], "plate_text": "...", "confidence": 0.9, "timestamp": float}
        self.lock = threading.Lock()

        # Thread
        self._thread: Optional[threading.Thread] = None
        self._reconnect = ReconnectManager(camera_id, label)

        # Health metrics
        self._started_at: Optional[float] = None
        self._total_frames: int = 0
        self._frames_published: int = 0
        self._last_frame_time: Optional[float] = None
        self._last_cleanup_time: float = 0.0

    @property
    def uptime_seconds(self) -> float:
        if self._started_at and self.running:
            return round(time.time() - self._started_at, 1)
        return 0.0

    @property
    def health(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "label": self.label,
            "running": self.running,
            "uptime_seconds": self.uptime_seconds,
            "total_frames_captured": self._total_frames,
            "frames_published_to_redis": self._frames_published,
            "reconnect_count": self._reconnect.attempt_count,
            "last_frame_age_seconds": (
                round(time.time() - self._last_frame_time, 1)
                if self._last_frame_time else None
            ),
            "source": str(self.source) if self.source else "",
        }

    def start(self, source):
        """Start the capture thread."""
        if self.running:
            return

        os.makedirs(settings.SNAPSHOT_DIR, exist_ok=True)
        self.source = source
        self.running = True
        self._total_frames = 0
        self._frames_published = 0
        self._last_frame_time = None
        self._started_at = time.time()
        self._reconnect = ReconnectManager(self.camera_id, self.label)

        self._thread = threading.Thread(
            target=self._capture_loop,
            args=(source,),
            daemon=True,
            name=f"Capture-{self.camera_id}",
        )
        self._thread.start()
        self._reconnect.log_started(str(source))

    def stop(self):
        """Stop the capture thread."""
        self.running = False
        self._started_at = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None
        self.current_frame = None
        self._reconnect.log_stopped()

    # ------------------------------------------------------------------
    # Capture loop — ONLY reads frames + publishes to Redis
    # ------------------------------------------------------------------
    def _capture_loop(self, source):
        while self.running:
            cap = cv2.VideoCapture(source)

            if not cap.isOpened():
                self._reconnect.wait_and_increment()
                continue

            # Connection successful — reset backoff
            self._reconnect.reset()
            frame_count = 0

            while self.running and cap.isOpened():
                ret, frame = cap.read()

                if not ret:
                    # Video file → loop; RTSP → reconnect
                    if isinstance(source, str) and not source.startswith("rtsp"):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        self._reconnect.log_frame_loss(str(source))
                        break

                frame_count += 1
                self._total_frames += 1
                self._last_frame_time = time.time()

                # --- Update MJPEG buffer (every frame for smooth streaming) ---
                annotated = frame.copy()
                now = time.time()
                with self.lock:
                    # Keep annotations that are less than 2 seconds old
                    self.active_annotations = [
                        a for a in self.active_annotations
                        if now - a.get("timestamp", 0) < 2.0
                    ]
                    for ann in self.active_annotations:
                        box = ann.get("box")
                        if box:
                            x1, y1, x2, y2 = box[:4]
                            plate_text = ann.get("plate_text", "")
                            conf = ann.get("confidence", 1.0)
                            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            label_text = f"{plate_text} {conf:.2f}" if plate_text else f"{conf:.2f}"
                            cv2.putText(annotated, label_text, (x1, y1 - 8),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # Camera label overlay on the frame
                cv2.putText(annotated, f"CAM {self.camera_id}: {self.label}",
                            (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                with self.lock:
                    _, jpeg = cv2.imencode(
                        '.jpg', annotated,
                        [cv2.IMWRITE_JPEG_QUALITY, 70],
                    )
                    self.current_frame = jpeg.tobytes()

                # --- Publish to Redis for OCR (throttled: every Nth frame) ---
                if frame_count % settings.FRAME_PUBLISH_INTERVAL == 0:
                    self._publish_frame(frame)

                # Yield CPU — ~30 FPS cap
                time.sleep(0.03)

            cap.release()

            # If still running, reconnect
            if self.running:
                self._reconnect.wait_and_increment()

    def _publish_frame(self, frame):
        """Encode frame as JPEG, base64-encode, push to Redis OCR queue."""
        try:
            _, jpeg_buf = cv2.imencode(
                '.jpg', frame,
                [cv2.IMWRITE_JPEG_QUALITY, 85],
            )
            frame_b64 = base64.b64encode(jpeg_buf.tobytes()).decode("ascii")

            task = json.dumps({
                "camera_id": self.camera_id,
                "camera_label": self.label,
                "frame_b64": frame_b64,
                "timestamp": time.time(),
            }).encode("utf-8")

            if push_ocr_task(task):
                self._frames_published += 1
            else:
                # Queue full — frame dropped (backpressure)
                log.debug("Camera %d: OCR queue full, frame dropped", self.camera_id)

        except Exception as e:
            log.warning("Camera %d: failed to publish frame: %s", self.camera_id, e)

    # ------------------------------------------------------------------
    # Publish camera health to Redis (for watchdog / health endpoint)
    # ------------------------------------------------------------------
    def publish_health(self):
        """Write current health metrics to Redis hash."""
        try:
            r = get_sync_redis()
            key = f"{Queues.CAMERA_HEALTH_PREFIX}{self.camera_id}"
            r.hset(key, mapping={
                "camera_id": str(self.camera_id),
                "label": self.label,
                "running": "1" if self.running else "0",
                "uptime": str(self.uptime_seconds),
                "total_frames": str(self._total_frames),
                "published": str(self._frames_published),
                "reconnects": str(self._reconnect.attempt_count),
            })
            r.expire(key, 60)  # Auto-expire if camera dies
        except Exception:
            pass
