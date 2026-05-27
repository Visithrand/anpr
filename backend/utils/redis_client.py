"""
backend/utils/redis_client.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Centralised Redis client for the ANPR system.

Provides:
  - Sync client   → used by camera_service and ocr_worker threads
  - Async client  → used by FastAPI async endpoints
  - Queue constants
  - Health check

Usage (sync):
    from backend.utils.redis_client import get_sync_redis, Queues
    r = get_sync_redis()
    r.lpush(Queues.OCR, data)

Usage (async):
    from backend.utils.redis_client import get_async_redis
    r = await get_async_redis()
    await r.publish(Queues.DETECTION_RESULTS, data)
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Optional

import redis
import redis.asyncio as aioredis

from backend.config import settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Queue / Channel Constants
# ---------------------------------------------------------------------------

class Queues:
    """Redis key names — single source of truth."""
    OCR = "anpr:ocr_queue"                      # List — frames waiting for OCR
    ENTRY_EVENTS = "anpr:entry_events"           # List — detected plates at entry cameras
    EXIT_EVENTS = "anpr:exit_events"             # List — detected plates at exit cameras
    DETECTION_RESULTS = "anpr:detection_results"  # Pub/Sub channel — OCR results to backend
    COOLDOWN_PREFIX = "anpr:cooldown:"           # String with TTL — dedup per plate
    CAMERA_HEALTH_PREFIX = "anpr:cam_health:"    # Hash — per-camera health data


# ---------------------------------------------------------------------------
# Sync Redis Client (for threads: camera_service, ocr_worker)
# ---------------------------------------------------------------------------

_sync_client: Optional[redis.Redis] = None
_sync_lock = threading.Lock()


def get_sync_redis() -> redis.Redis:
    """Return a thread-safe sync Redis client singleton."""
    global _sync_client
    if _sync_client is not None:
        return _sync_client

    with _sync_lock:
        if _sync_client is not None:
            return _sync_client

        _sync_client = redis.Redis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=False,  # We handle binary (JPEG frames)
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        log.info("Sync Redis client connected: %s", settings.REDIS_URL)
        return _sync_client


# ---------------------------------------------------------------------------
# Async Redis Client (for FastAPI async endpoints)
# ---------------------------------------------------------------------------

_async_client: Optional[aioredis.Redis] = None


async def get_async_redis() -> aioredis.Redis:
    """Return an async Redis client singleton."""
    global _async_client
    if _async_client is not None:
        return _async_client

    _async_client = aioredis.from_url(
        settings.REDIS_URL,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    log.info("Async Redis client connected: %s", settings.REDIS_URL)
    return _async_client


async def close_async_redis():
    """Close the async Redis connection (call on shutdown)."""
    global _async_client
    if _async_client:
        await _async_client.aclose()
        _async_client = None
        log.info("Async Redis client closed")


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

def redis_health() -> dict:
    """Check Redis connectivity and return stats."""
    try:
        r = get_sync_redis()
        r.ping()
        info = r.info(section="memory")
        ocr_queue_len = r.llen(Queues.OCR)
        entry_queue_len = r.llen(Queues.ENTRY_EVENTS)
        exit_queue_len = r.llen(Queues.EXIT_EVENTS)

        return {
            "status": "healthy",
            "url": settings.REDIS_URL,
            "memory_used_mb": round(info.get("used_memory", 0) / (1024 * 1024), 2),
            "queues": {
                "ocr_queue": ocr_queue_len,
                "entry_events": entry_queue_len,
                "exit_events": exit_queue_len,
            },
        }
    except Exception as e:
        log.warning("Redis health check failed: %s", e)
        return {
            "status": "unhealthy",
            "url": settings.REDIS_URL,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Convenience: Cooldown (plate dedup via Redis TTL)
# ---------------------------------------------------------------------------

def check_and_set_cooldown(plate_number: str, cooldown_seconds: int = 30) -> bool:
    """
    Check if a plate is in cooldown.

    Returns True if the plate is NEW (not in cooldown) and sets the cooldown.
    Returns False if the plate is still in cooldown (skip it).

    Uses Redis SET NX EX for atomic check-and-set.
    """
    r = get_sync_redis()
    key = f"{Queues.COOLDOWN_PREFIX}{plate_number}"
    # SET key value NX EX seconds → returns True if set (new), None if exists
    result = r.set(key, "1", nx=True, ex=cooldown_seconds)
    return result is not None


# ---------------------------------------------------------------------------
# Convenience: Publish detection result
# ---------------------------------------------------------------------------

def publish_detection(detection_data: dict):
    """Publish an OCR detection result to the Pub/Sub channel."""
    r = get_sync_redis()
    r.publish(Queues.DETECTION_RESULTS, json.dumps(detection_data).encode("utf-8"))


def push_ocr_task(task_data: bytes):
    """Push a frame to the OCR queue. Drops if queue is too large."""
    r = get_sync_redis()
    queue_len = r.llen(Queues.OCR)
    if queue_len >= settings.REDIS_QUEUE_MAX_SIZE:
        # Drop frame — OCR can't keep up, don't let queue grow unbounded
        return False
    r.lpush(Queues.OCR, task_data)
    return True
