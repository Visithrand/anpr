"""
camera_service/watchdog.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Watchdog service to monitor the health of camera capture threads.

Detects stale feeds (no new frames for 60s), restarts them,
and periodically publishes health status to Redis.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Any, Optional

from backend.config import settings
from backend.utils.database import SessionLocal
from backend.models.models import SystemLog

log = logging.getLogger(__name__)


def _write_system_log(service: str, level: str, message: str):
    """Write an entry to the SystemLog table."""
    try:
        with SessionLocal() as db:
            db.add(SystemLog(
                service_name=service,
                level=level,
                message=message,
            ))
            db.commit()
    except Exception as e:
        log.warning("Failed to write watchdog SystemLog: %s", e)


class CameraWatchdog:
    """
    Monitors camera capture feeds.
    - Periodically triggers camera health publish to Redis.
    - Detects stale capture threads (no frame in settings.WATCHDOG_STALE_THRESHOLD).
    - Auto-restarts stalled or stopped camera captures.
    """

    def __init__(self, camera_manager, interval: int = 15):
        self.camera_manager = camera_manager
        self.interval = interval
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        """Start the watchdog background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="CameraWatchdog",
        )
        self._thread.start()
        log.info("CameraWatchdog started with interval %ds", self.interval)

    def stop(self):
        """Stop the watchdog thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None
        log.info("CameraWatchdog stopped")

    def _loop(self):
        while self._running:
            try:
                self._check_and_publish()
            except Exception as e:
                log.error("Error in CameraWatchdog loop: %s", e, exc_info=True)
            time.sleep(self.interval)

    def _check_and_publish(self):
        """Check all configured cameras and publish their health to Redis."""
        # Get active feeds from the camera manager
        for cam_id in range(1, settings.MAX_CAMERAS + 1):
            feed = self.camera_manager.get_feed(cam_id)
            cam_cfg = settings.camera_defaults.get(cam_id)

            if not cam_cfg:
                continue

            if feed is None or not feed.running:
                # Camera is supposed to be auto-started or was stopped unexpectedly
                if settings.CAMERA_AUTO_START:
                    log.warning("CameraWatchdog: Camera %d is not running. Restarting...", cam_id)
                    _write_system_log(
                        "camera_watchdog", "WARNING",
                        f"Camera {cam_id} ({cam_cfg['label']}) found dead — restarting"
                    )
                    source = cam_cfg["source"]
                    src = int(source) if source.isdigit() else source
                    try:
                        self.camera_manager.start_camera(cam_id, src, cam_cfg["label"])
                        log.info("CameraWatchdog: Camera %d restarted successfully", cam_id)
                    except Exception as e:
                        log.error("CameraWatchdog: Failed to restart camera %d: %s", cam_id, e)
            else:
                # Camera is running, check if it's stale
                last_frame = feed._last_frame_time
                now = time.time()
                if last_frame and (now - last_frame) > 60:
                    log.warning(
                        "CameraWatchdog: Camera %d stream is stale (last frame %.1fs ago). Restarting...",
                        cam_id, now - last_frame
                    )
                    _write_system_log(
                        "camera_watchdog", "WARNING",
                        f"Camera {cam_id} stream stale (last frame {now - last_frame:.1f}s ago) — restarting"
                    )
                    # Restart camera feed
                    source = feed.source
                    label = feed.label
                    try:
                        feed.stop()
                        self.camera_manager.start_camera(cam_id, source, label)
                        log.info("CameraWatchdog: Camera %d restarted due to staleness", cam_id)
                    except Exception as e:
                        log.error("CameraWatchdog: Failed to restart stale camera %d: %s", cam_id, e)

                # Periodically publish metrics to Redis
                try:
                    feed.publish_health()
                except Exception as e:
                    log.debug("Failed to publish health for camera %d: %s", cam_id, e)
