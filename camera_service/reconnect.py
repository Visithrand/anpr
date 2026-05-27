"""
camera_service/reconnect.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
RTSP/camera reconnection with exponential backoff.

Extracted from the monolithic CameraFeed so the logic is reusable
and testable independently.
"""

from __future__ import annotations

import logging
import time

from backend.config import settings
from backend.utils.database import SessionLocal
from backend.models.models import CameraLog

log = logging.getLogger(__name__)


class ReconnectManager:
    """
    Manages camera reconnection with exponential backoff.

    Tracks:
      - reconnect attempt count
      - current delay
      - camera lifecycle events → CameraLog table
    """

    def __init__(self, camera_id: int, label: str = "Camera"):
        self.camera_id = camera_id
        self.label = label
        self.attempt_count: int = 0
        self._current_delay: float = settings.CAMERA_RECONNECT_BASE_DELAY

    def reset(self):
        """Reset backoff after a successful connection."""
        if self.attempt_count > 0:
            log.info(
                "Camera %d: reconnected after %d attempts",
                self.camera_id, self.attempt_count,
            )
            self._log_event(
                "RECONNECT",
                f"Reconnected successfully after {self.attempt_count} attempts",
            )
        self.attempt_count = 0
        self._current_delay = settings.CAMERA_RECONNECT_BASE_DELAY

    def wait_and_increment(self):
        """Sleep for the current backoff delay, then increase it."""
        self.attempt_count += 1
        log.warning(
            "Camera %d: reconnecting in %.1fs (attempt %d)",
            self.camera_id, self._current_delay, self.attempt_count,
        )
        self._log_event(
            "RECONNECT",
            f"Retry in {self._current_delay:.1f}s (attempt {self.attempt_count})",
        )
        time.sleep(self._current_delay)
        self._current_delay = min(
            self._current_delay * 2,
            settings.CAMERA_RECONNECT_MAX_DELAY,
        )

    def log_started(self, source: str):
        log.info("Camera %d started — source=%s", self.camera_id, source)
        self._log_event("STARTED", f"source={source}")

    def log_stopped(self):
        log.info("Camera %d stopped", self.camera_id)
        self._log_event("STOPPED")

    def log_frame_loss(self, source: str):
        log.warning("Camera %d: stream interrupted", self.camera_id)
        self._log_event("FRAME_LOSS", f"Stream read failed — source={source}")

    def log_error(self, error: str):
        log.error("Camera %d: error — %s", self.camera_id, error)
        self._log_event("ERROR", error)

    def _log_event(self, event: str, details: str = ""):
        """Write camera lifecycle event to DB."""
        try:
            with SessionLocal() as db:
                db.add(CameraLog(
                    camera_id=self.camera_id,
                    camera_label=self.label,
                    event=event,
                    details=details,
                ))
                db.commit()
        except Exception as e:
            log.debug("Failed to log camera event: %s", e)
