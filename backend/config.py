"""
backend/config.py
~~~~~~~~~~~~~~~~~
Centralised, validated configuration using pydantic-settings.

Every module imports `settings` from here — the single source of truth.
All values are loaded from the `.env` file (or environment variables)
and validated at application startup. A bad configuration will cause an
immediate, descriptive error rather than a silent runtime failure.

Usage:
    from backend.config import settings
    print(settings.DATABASE_URL)
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


# ---------------------------------------------------------------------------
# Resolve project root — two levels up from this file (backend/config.py)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """
    Application settings — loaded from .env and environment variables.
    Environment variables always override .env values.
    """

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql://postgres:visithran%40123@localhost:5432/post",
        description="SQLAlchemy database connection URL",
    )
    DB_POOL_SIZE: int = Field(default=10, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0, le=200)
    DB_POOL_RECYCLE: int = Field(
        default=3600,
        description="Seconds before a pooled connection is recycled (prevents stale connections in 24/7 operation)",
    )
    DB_POOL_PRE_PING: bool = Field(
        default=True,
        description="Test connections before use — detects disconnected DB",
    )

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    REDIS_MAX_CONNECTIONS: int = Field(default=20, ge=1)
    REDIS_QUEUE_MAX_SIZE: int = Field(
        default=500, ge=10,
        description="Max OCR queue depth — frames dropped if exceeded (backpressure)",
    )

    # ------------------------------------------------------------------
    # OCR Worker
    # ------------------------------------------------------------------
    OCR_WORKER_COUNT: int = Field(
        default=1, ge=1, le=8,
        description="Number of OCR worker threads",
    )
    FRAME_PUBLISH_INTERVAL: int = Field(
        default=6, ge=1, le=15,
        description="Publish every Nth frame to Redis for OCR (throttling)",
    )

    # ------------------------------------------------------------------
    # ANPR / Model
    # ------------------------------------------------------------------
    OPENVINO_MODEL_PATH: str = Field(
        default="backend/models/plate_det/openvino/best.xml",
        description="Path to the OpenVINO plate detection model",
    )
    PLATE_CONFIDENCE_THRESHOLD: float = Field(
        default=0.35, ge=0.0, le=1.0,
        description="Minimum confidence for plate detection",
    )
    OCR_SERVICE_URL: str = Field(
        default="http://127.0.0.1:8001/ocr",
        description="URL of the PaddleOCR microservice",
    )
    OCR_TIMEOUT_SECONDS: float = Field(default=5.0, ge=1.0)
    PLATE_COOLDOWN_SECONDS: int = Field(
        default=60, ge=5,
        description="Seconds before the same plate is re-detected",
    )

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------
    MAX_CAMERAS: int = Field(default=4, ge=1, le=16)
    CAMERA_1_SOURCE: str = Field(default="")
    CAMERA_1_LABEL: str = Field(default="Entry Gate 1")
    CAMERA_2_SOURCE: str = Field(default="")
    CAMERA_2_LABEL: str = Field(default="Entry Gate 2")
    CAMERA_3_SOURCE: str = Field(default="")
    CAMERA_3_LABEL: str = Field(default="Exit Gate 1")
    CAMERA_4_SOURCE: str = Field(default="")
    CAMERA_4_LABEL: str = Field(default="Exit Gate 2")
    CAMERA_RECONNECT_BASE_DELAY: float = Field(
        default=2.0,
        description="Initial delay (seconds) before camera reconnection attempt",
    )
    CAMERA_RECONNECT_MAX_DELAY: float = Field(
        default=60.0,
        description="Maximum delay (seconds) between reconnection attempts (exponential backoff cap)",
    )
    CAMERA_AUTO_START: bool = Field(
        default=True,
        description="Auto-start cameras configured in .env on application startup",
    )
    ENTRY_CAMERA_IDS: str = Field(
        default="1,2,3,4",
        description="Comma-separated camera IDs that act as ENTRY gates. "
                    "Detections from these cameras create Entry records.",
    )
    EXIT_CAMERA_IDS: str = Field(
        default="",
        description="Comma-separated camera IDs that act as EXIT gates. "
                    "Detections from these cameras process Exit records. "
                    "A camera can be in BOTH lists for dual-purpose use.",
    )

    # ------------------------------------------------------------------
    # Gate / Relay
    # ------------------------------------------------------------------
    GATE_API_URL: str = Field(
        default="http://localhost:9000",
        description="URL of the HTTP-based gate relay controller",
    )
    RELAY_TYPE: str = Field(
        default="http",
        description="Relay backend type: 'http', 'usb', 'gpio', 'simulated'",
    )
    RELAY_PORT: str = Field(
        default="",
        description="Serial port for USB relay (e.g., COM3 or /dev/ttyUSB0)",
    )
    GATE_OPEN_DURATION: int = Field(
        default=10, ge=3, le=60,
        description="Seconds to hold gate open before auto-close",
    )
    GATE_COOLDOWN_SECONDS: int = Field(
        default=5, ge=1,
        description="Minimum seconds between consecutive gate triggers (anti-rapid-trigger)",
    )

    # ------------------------------------------------------------------
    # Billing / SAP
    # ------------------------------------------------------------------
    BILLING_API_URL: str = Field(
        default="http://localhost:9001",
        description="Base URL of the external billing system",
    )
    BILLING_BACKEND: str = Field(
        default="http",
        description="Billing backend type: 'sap', 'http', 'mock'",
    )
    SAP_API_URL: str = Field(default="", description="SAP system base URL")
    SAP_API_KEY: str = Field(default="", description="SAP API authentication key")
    SAP_CLIENT_ID: str = Field(default="", description="SAP OAuth client ID")
    SAP_CLIENT_SECRET: str = Field(default="", description="SAP OAuth client secret")
    SAP_TIMEOUT: float = Field(default=10.0, ge=1.0)
    SAP_MAX_RETRIES: int = Field(default=3, ge=0, le=10)
    BILLING_CIRCUIT_BREAKER_THRESHOLD: int = Field(
        default=5, ge=1,
        description="Consecutive failures before circuit breaker opens",
    )
    BILLING_CIRCUIT_BREAKER_COOLDOWN: int = Field(
        default=60, ge=10,
        description="Seconds to wait before retrying after circuit breaker opens",
    )

    # ------------------------------------------------------------------
    # Auth / Security
    # ------------------------------------------------------------------
    JWT_SECRET_KEY: str = Field(
        default="anpr-os-secret-key-change-in-production-2026",
        description="Secret key for JWT token signing — CHANGE IN PRODUCTION",
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_HOURS: int = Field(default=24, ge=1)
    CORS_ORIGINS: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins",
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO", description="Root log level: DEBUG, INFO, WARNING, ERROR")
    LOG_DIR: str = Field(default="logs", description="Directory for log files")
    LOG_MAX_BYTES: int = Field(default=10 * 1024 * 1024, description="Max bytes per log file before rotation")
    LOG_BACKUP_COUNT: int = Field(default=5, description="Number of rotated log files to keep")

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------
    SNAPSHOT_DIR: str = Field(default="static/plates")
    SNAPSHOT_RETENTION_DAYS: int = Field(
        default=30, ge=1,
        description="Auto-delete snapshots older than this many days",
    )
    WATCHDOG_INTERVAL_SECONDS: int = Field(
        default=30, ge=10,
        description="Seconds between watchdog health checks",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper().strip()
        if v not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got '{v}'")
        return v

    @field_validator("RELAY_TYPE")
    @classmethod
    def validate_relay_type(cls, v: str) -> str:
        allowed = {"http", "usb", "gpio", "simulated"}
        v = v.lower().strip()
        if v not in allowed:
            raise ValueError(f"RELAY_TYPE must be one of {allowed}, got '{v}'")
        return v

    @field_validator("BILLING_BACKEND")
    @classmethod
    def validate_billing_backend(cls, v: str) -> str:
        allowed = {"sap", "http", "mock"}
        v = v.lower().strip()
        if v not in allowed:
            raise ValueError(f"BILLING_BACKEND must be one of {allowed}, got '{v}'")
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        return v.strip()

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------
    @property
    def cors_origin_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def camera_defaults(self) -> Dict[int, dict]:
        """Return pre-configured camera sources from settings."""
        cameras = {}
        for i in range(1, self.MAX_CAMERAS + 1):
            source = getattr(self, f"CAMERA_{i}_SOURCE", "").strip()
            label = getattr(self, f"CAMERA_{i}_LABEL", f"Camera {i}").strip()
            if source:
                cameras[i] = {"source": source, "label": label}
        return cameras

    @property
    def entry_camera_set(self) -> set:
        """Parse ENTRY_CAMERA_IDS into a set of ints."""
        if not self.ENTRY_CAMERA_IDS.strip():
            return set()
        return {int(x.strip()) for x in self.ENTRY_CAMERA_IDS.split(",") if x.strip().isdigit()}

    @property
    def exit_camera_set(self) -> set:
        """Parse EXIT_CAMERA_IDS into a set of ints."""
        if not self.EXIT_CAMERA_IDS.strip():
            return set()
        return {int(x.strip()) for x in self.EXIT_CAMERA_IDS.split(",") if x.strip().isdigit()}

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


# ---------------------------------------------------------------------------
# Singleton accessor — cached so settings are loaded once
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application settings singleton."""
    return Settings()


# Convenience alias — import this everywhere
settings = get_settings()

# ---------------------------------------------------------------------------
# Legacy aliases (backward compatibility for existing imports)
# ---------------------------------------------------------------------------
OPENVINO_MODEL_PATH = settings.OPENVINO_MODEL_PATH
MAX_CAMERAS = settings.MAX_CAMERAS
CAMERA_DEFAULTS = settings.camera_defaults
