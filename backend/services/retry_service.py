"""
backend/services/retry_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generic retry and circuit breaker utilities for external API calls.

Retry decorator:
  - Configurable max attempts, base delay, backoff multiplier
  - Configurable exception types to retry on
  - Exponential backoff with optional jitter

Circuit breaker:
  - Opens after N consecutive failures (stops calling the service)
  - Half-opens after a cooldown period (allows one test call)
  - Closes on success (resumes normal operation)
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
import threading
from typing import Callable, Optional, Set, Tuple, Type

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async Retry Decorator
# ---------------------------------------------------------------------------

def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator for async functions — retries on specified exceptions.

    Example::

        @async_retry(max_attempts=3, base_delay=1.0, retry_on=(httpx.HTTPError,))
        async def call_billing_api(plate: str) -> dict:
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            delay = base_delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e
                    if attempt == max_attempts:
                        log.error(
                            "%s failed after %d attempts: %s",
                            func.__name__, max_attempts, e,
                        )
                        raise

                    actual_delay = delay
                    if jitter:
                        actual_delay += random.uniform(0, delay * 0.3)
                    actual_delay = min(actual_delay, max_delay)

                    log.warning(
                        "%s attempt %d/%d failed: %s — retrying in %.1fs",
                        func.__name__, attempt, max_attempts, e, actual_delay,
                    )
                    await asyncio.sleep(actual_delay)
                    delay *= backoff_multiplier

            raise last_exception  # Should not reach here

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.

    States:
      - CLOSED:    normal operation, calls pass through
      - OPEN:      service is down, calls are rejected immediately
      - HALF_OPEN: one test call is allowed to check if service recovered

    Usage::

        breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=60)

        if not breaker.can_execute():
            return {"error": "Service temporarily unavailable"}

        try:
            result = await call_api()
            breaker.record_success()
            return result
        except Exception:
            breaker.record_failure()
            raise
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: int = 60,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.name = name

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN:
                # Check if cooldown has passed → transition to HALF_OPEN
                if self._last_failure_time and \
                   (time.time() - self._last_failure_time) >= self.cooldown_seconds:
                    self._state = self.HALF_OPEN
                    log.info(
                        "CircuitBreaker '%s': OPEN → HALF_OPEN (cooldown expired)",
                        self.name,
                    )
            return self._state

    def can_execute(self) -> bool:
        """Check if a call should be allowed through."""
        current_state = self.state
        if current_state == self.CLOSED:
            return True
        if current_state == self.HALF_OPEN:
            return True  # Allow one test call
        return False  # OPEN

    def record_success(self):
        """Record a successful call — reset the breaker."""
        with self._lock:
            if self._state == self.HALF_OPEN:
                log.info(
                    "CircuitBreaker '%s': HALF_OPEN → CLOSED (success)",
                    self.name,
                )
            self._state = self.CLOSED
            self._failure_count = 0

    def record_failure(self):
        """Record a failed call — may trip the breaker."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == self.HALF_OPEN:
                self._state = self.OPEN
                log.warning(
                    "CircuitBreaker '%s': HALF_OPEN → OPEN (test call failed)",
                    self.name,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                log.warning(
                    "CircuitBreaker '%s': CLOSED → OPEN (threshold %d reached)",
                    self.name, self.failure_threshold,
                )

    def reset(self):
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = self.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            log.info("CircuitBreaker '%s': manually reset", self.name)

    @property
    def info(self) -> dict:
        """Return breaker state for health endpoints."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "cooldown_seconds": self.cooldown_seconds,
        }
