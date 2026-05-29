"""
backend/services/watchdog.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Background watchdog service for 24/7 system health monitoring.

Runs as a daemon thread, periodically checking:
  - Camera feeds are alive (restarts dead feeds)
  - Database connectivity
  - OCR service health
  - Disk space for snapshots
  - Snapshot directory cleanup (old files)

Writes alerts to the SystemLog table for operational monitoring.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import httpx

from backend.config import settings
from backend.utils.database import SessionLocal, engine
from backend.models.models import SystemLog
from backend.utils.helpers import cleanup_old_snapshots, get_disk_usage, count_files_in_dir

log = logging.getLogger(__name__)


def _write_system_log(service: str, level: str, message: str, traceback_str: str = ""):
    """Write an entry to the SystemLog table."""
    try:
        with SessionLocal() as db:
            db.add(SystemLog(
                service_name=service,
                level=level,
                message=message,
                traceback=traceback_str or None,
            ))
            db.commit()
    except Exception as e:
        log.warning("Failed to write SystemLog: %s", e)


class WatchdogService:
    """
    Background health monitor that runs every N seconds.

    Checks:
      1. Camera feeds — restarts any that have died
      2. Database — verifies connection is alive
      3. OCR service — pings the health endpoint
      4. Disk space — warns if low
      5. Snapshot cleanup — deletes old plate images
    """

    def __init__(self, interval: int = 30):
        self.interval = interval
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._check_count = 0

    def start(self):
        """Start the watchdog background thread."""
        if self._running:
            log.warning("Watchdog is already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="Watchdog",
        )
        self._thread.start()
        log.info("Watchdog started — interval=%ds", self.interval)
        _write_system_log("watchdog", "INFO", f"Watchdog started — interval={self.interval}s")

    def stop(self):
        """Stop the watchdog."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None
        log.info("Watchdog stopped")

    def _loop(self):
        """Main watchdog loop."""
        while self._running:
            try:
                self._check_count += 1
                self._run_checks()
            except Exception as e:
                log.error("Watchdog check failed: %s", e)
                _write_system_log("watchdog", "ERROR", f"Health check failed: {e}")

            time.sleep(self.interval)

    def _run_checks(self):
        """Execute all health checks."""
        # 1. Check cameras
        self._check_cameras()

        # 2. Check database
        self._check_database()

        # 3. Check OCR service (every 5th check to avoid spamming)
        if self._check_count % 5 == 0:
            self._check_ocr_service()

        # 4. Check disk space (every 10th check)
        if self._check_count % 10 == 0:
            self._check_disk_space()

        # 5. Snapshot cleanup (every 60th check ≈ 30 minutes)
        if self._check_count % 60 == 0:
            self._cleanup_snapshots()

        # 6. Check Redis health (every 2nd check)
        if self._check_count % 2 == 0:
            self._check_redis()

    def _check_cameras(self):
        """Check if configured cameras are still running, restart if dead."""
        try:
            # Import here to avoid circular imports
            from backend.routes.live import camera_mgr

            for cam_id, cam_cfg in settings.camera_defaults.items():
                feed = camera_mgr.get_feed(cam_id)

                if feed is None or not feed.running:
                    log.warning(
                        "Watchdog: camera %d (%s) is not running — restarting",
                        cam_id, cam_cfg["label"],
                    )
                    _write_system_log(
                        "watchdog", "WARNING",
                        f"Camera {cam_id} ({cam_cfg['label']}) found dead — restarting",
                    )
                    source = cam_cfg["source"]
                    src = int(source) if source.isdigit() else source
                    try:
                        camera_mgr.start_camera(cam_id, src, cam_cfg["label"])
                        log.info("Watchdog: camera %d restarted successfully", cam_id)
                        _write_system_log(
                            "watchdog", "INFO",
                            f"Camera {cam_id} restarted successfully",
                        )
                    except Exception as e:
                        log.error("Watchdog: failed to restart camera %d: %s", cam_id, e)
                        _write_system_log(
                            "watchdog", "ERROR",
                            f"Failed to restart camera {cam_id}: {e}",
                        )
                else:
                    # Check for stale frames (no new frame for 60 seconds)
                    if feed._last_frame_time and (time.time() - feed._last_frame_time) > 60:
                        log.warning(
                            "Watchdog: camera %d has stale frames (%.0fs old)",
                            cam_id, time.time() - feed._last_frame_time,
                        )
                        _write_system_log(
                            "watchdog", "WARNING",
                            f"Camera {cam_id} has stale frames — last frame {time.time() - feed._last_frame_time:.0f}s ago",
                        )

        except Exception as e:
            log.error("Watchdog camera check failed: %s", e)

    def _check_database(self):
        """Verify database connection is alive."""
        try:
            with engine.connect() as conn:
                conn.execute(conn.default_isolation_level if hasattr(conn, 'default_isolation_level') else None or conn.connection)
        except Exception:
            pass

        try:
            with SessionLocal() as db:
                db.execute(db.bind.dialect.do_ping(db.bind) if hasattr(db.bind.dialect, 'do_ping') else None)
        except Exception:
            pass

        # Simplified: just try to create a session
        try:
            with SessionLocal() as db:
                from sqlalchemy import text
                db.execute(text("SELECT 1"))
                log.debug("Watchdog: database OK")
        except Exception as e:
            log.error("Watchdog: database check FAILED — %s", e)
            _write_system_log("watchdog", "CRITICAL", f"Database connectivity lost: {e}")

    def _check_ocr_service(self):
        """Ping the OCR microservice health endpoint."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(settings.OCR_SERVICE_URL)
            base_url = f"{parsed.scheme}://{parsed.netloc}/"
                
            resp = httpx.get(
                base_url,
                timeout=5.0,
            )
            if resp.status_code == 200:
                log.debug("Watchdog: OCR service OK")
            else:
                log.warning("Watchdog: OCR service returned HTTP %d", resp.status_code)
                _write_system_log(
                    "watchdog", "WARNING",
                    f"OCR service returned HTTP {resp.status_code}",
                )
        except Exception as e:
            log.warning("Watchdog: OCR service unreachable — %s", e)
            _write_system_log(
                "watchdog", "WARNING",
                f"OCR service unreachable: {e}",
            )

    def _check_disk_space(self):
        """Check disk space and warn if low."""
        usage = get_disk_usage(".")
        if "error" in usage:
            return

        if usage.get("free_gb", 999) < 5.0:
            log.warning(
                "Watchdog: LOW DISK SPACE — %.1f GB free (%.1f%% used)",
                usage["free_gb"], usage["percent_used"],
            )
            _write_system_log(
                "watchdog", "WARNING",
                f"Low disk space: {usage['free_gb']:.1f} GB free ({usage['percent_used']:.1f}% used)",
            )

        snapshot_count = count_files_in_dir(settings.SNAPSHOT_DIR)
        log.debug(
            "Watchdog: disk=%.1f GB free, snapshots=%d files",
            usage.get("free_gb", 0), snapshot_count,
        )

    def _cleanup_snapshots(self):
        """Delete old snapshot images beyond retention period."""
        deleted = cleanup_old_snapshots(
            settings.SNAPSHOT_DIR,
            settings.SNAPSHOT_RETENTION_DAYS,
        )
        if deleted > 0:
            _write_system_log(
                "watchdog", "INFO",
                f"Snapshot cleanup: deleted {deleted} files older than {settings.SNAPSHOT_RETENTION_DAYS} days",
            )

    def _check_redis(self):
        """Verify Redis is running and monitor queue depth."""
        try:
            from backend.utils.redis_client import redis_health
            r_health = redis_health()
            if r_health.get("status") != "healthy":
                _write_system_log(
                    "watchdog", "CRITICAL",
                    f"Redis connection failed: {r_health.get('error', 'unknown error')}"
                )
            else:
                ocr_queue_len = r_health.get("queues", {}).get("ocr_queue", 0)
                if ocr_queue_len > 100:
                    log.warning("Watchdog: Redis OCR queue is high (%d items)", ocr_queue_len)
                    _write_system_log(
                        "watchdog", "WARNING",
                        f"Redis OCR queue depth is high ({ocr_queue_len} items). Worker might be lagging or offline."
                    )
        except Exception as e:
            log.error("Watchdog: Redis check failed — %s", e)


# Singleton instance
watchdog = WatchdogService(interval=settings.WATCHDOG_INTERVAL_SECONDS)
