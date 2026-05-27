"""
backend/utils/logger.py
~~~~~~~~~~~~~~~~~~~~~~~~
Production logging configuration with rotating file handlers.

Call ``setup_logging()`` once during application startup (in ``main.py``
lifespan).  After that, every module uses the standard library:

    import logging
    log = logging.getLogger(__name__)
    log.info("message")

Log files are written to the ``logs/`` directory with automatic rotation:
  - app.log      → general application logs
  - camera.log   → camera feed events (start / stop / reconnect / error)
  - gate.log     → gate open / close events
  - billing.log  → billing API requests and responses
  - error.log    → ERROR and above from all loggers (catch-all)
"""

from __future__ import annotations

import logging
import logging.config
import os
import sys
from pathlib import Path


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """
    Initialise the logging subsystem.

    Parameters
    ----------
    log_dir : str
        Directory for log files.  Created if it doesn't exist.
    log_level : str
        Root log level (DEBUG / INFO / WARNING / ERROR / CRITICAL).
    max_bytes : int
        Maximum size of a single log file before rotation.
    backup_count : int
        Number of rotated log files to keep per handler.
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    config: dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": log_format,
                "datefmt": date_format,
            },
            "brief": {
                "format": "%(levelname)-8s | %(name)s | %(message)s",
            },
        },
        "handlers": {
            # ---- Console (stdout) ----
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "brief",
                "stream": "ext://sys.stdout",
            },
            # ---- Rotating file: general application ----
            "file_app": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": str(log_path / "app.log"),
                "maxBytes": max_bytes,
                "backupCount": backup_count,
                "encoding": "utf-8",
            },
            # ---- Rotating file: camera events ----
            "file_camera": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": str(log_path / "camera.log"),
                "maxBytes": max_bytes,
                "backupCount": backup_count,
                "encoding": "utf-8",
            },
            # ---- Rotating file: gate / relay events ----
            "file_gate": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": str(log_path / "gate.log"),
                "maxBytes": max_bytes,
                "backupCount": backup_count,
                "encoding": "utf-8",
            },
            # ---- Rotating file: billing / SAP events ----
            "file_billing": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": str(log_path / "billing.log"),
                "maxBytes": max_bytes,
                "backupCount": backup_count,
                "encoding": "utf-8",
            },
            # ---- Error catch-all (ERROR+ from all loggers) ----
            "file_error": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "standard",
                "filename": str(log_path / "error.log"),
                "maxBytes": max_bytes,
                "backupCount": backup_count,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            # Camera-related loggers → camera.log
            "backend.routes.live": {
                "handlers": ["console", "file_camera", "file_error"],
                "level": "DEBUG",
                "propagate": False,
            },
            "backend.services.anpr_service": {
                "handlers": ["console", "file_camera", "file_error"],
                "level": "DEBUG",
                "propagate": False,
            },
            "anpr": {
                "handlers": ["console", "file_camera", "file_error"],
                "level": "DEBUG",
                "propagate": False,
            },
            # Gate / relay loggers → gate.log
            "backend.services.gate_trigger": {
                "handlers": ["console", "file_gate", "file_error"],
                "level": "DEBUG",
                "propagate": False,
            },
            "backend.services.relay_controller": {
                "handlers": ["console", "file_gate", "file_error"],
                "level": "DEBUG",
                "propagate": False,
            },
            # Billing loggers → billing.log
            "backend.services.billing_service": {
                "handlers": ["console", "file_billing", "file_error"],
                "level": "DEBUG",
                "propagate": False,
            },
            "backend.services.sap_client": {
                "handlers": ["console", "file_billing", "file_error"],
                "level": "DEBUG",
                "propagate": False,
            },
            "backend.routes.billing": {
                "handlers": ["console", "file_billing", "file_error"],
                "level": "DEBUG",
                "propagate": False,
            },
            # Watchdog
            "backend.services.watchdog": {
                "handlers": ["console", "file_app", "file_error"],
                "level": "DEBUG",
                "propagate": False,
            },
            # Suppress noisy third-party loggers
            "uvicorn": {"level": "INFO"},
            "uvicorn.access": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "ppocr": {"level": "WARNING"},
            "paddle": {"level": "WARNING"},
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file_app", "file_error"],
        },
    }

    logging.config.dictConfig(config)
    logging.getLogger(__name__).info(
        "Logging initialised — level=%s, dir=%s, max_bytes=%s, backups=%d",
        log_level, log_path.resolve(), max_bytes, backup_count,
    )
