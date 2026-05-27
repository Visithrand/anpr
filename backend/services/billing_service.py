"""
backend/services/billing_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Centralized service for all billing-related operations.

Supports multiple billing backends via BILLING_BACKEND config:
  - "sap"  → SAPBillingClient (SAP system integration)
  - "http" → Generic HTTP billing API (original behavior)
  - "mock" → Always returns paid=True (for development/testing)

Third-party billing flow:
  - Entry is registered and a PENDING billing record is created
  - A third-party system (POS, cashier, UPI, SAP) handles payment collection
  - On exit, we query the billing backend to confirm payment
  - If paid → gate opens; if not paid → gate stays closed

External Billing API contract (HTTP backend):
  CHECK PAYMENT:
    GET {BILLING_API_URL}/payment/status?plate=<plate_number>
    Response: {"paid": true/false, "amount": 150.0, "reference": "TXN-ABC123", "message": "..."}
"""

from __future__ import annotations

import json
import logging
import time

import httpx

from backend.config import settings
from backend.services.retry_service import CircuitBreaker, async_retry
from backend.utils.database import SessionLocal
from backend.models.models import PaymentLog

log = logging.getLogger(__name__)

# Circuit breaker for the HTTP billing backend
_http_breaker = CircuitBreaker(
    failure_threshold=settings.BILLING_CIRCUIT_BREAKER_THRESHOLD,
    cooldown_seconds=settings.BILLING_CIRCUIT_BREAKER_COOLDOWN,
    name="http_billing",
)


def _log_payment(
    plate_number: str,
    api_url: str = "",
    request_payload: str = "",
    response_payload: str = "",
    status_code: int | None = None,
    latency_ms: float | None = None,
    api_reachable: bool = True,
    error_message: str = "",
):
    """Write a billing API call record to the PaymentLog table."""
    try:
        with SessionLocal() as db:
            db.add(PaymentLog(
                plate_number=plate_number,
                api_url=api_url,
                request_payload=request_payload,
                response_payload=response_payload,
                status_code=status_code,
                latency_ms=latency_ms,
                api_reachable=api_reachable,
                error_message=error_message,
            ))
            db.commit()
    except Exception as e:
        log.warning("Failed to write PaymentLog: %s", e)


# ---------------------------------------------------------------------------
# HTTP Billing Backend (original behavior — preserved)
# ---------------------------------------------------------------------------

async def _check_payment_http(plate_number: str) -> dict:
    """Query the external HTTP billing API for payment status."""
    url = f"{settings.BILLING_API_URL.rstrip('/')}/payment/status"

    if not _http_breaker.can_execute():
        log.warning("HTTP billing circuit breaker OPEN — skipping for %s", plate_number)
        _log_payment(
            plate_number=plate_number,
            api_url=url,
            api_reachable=False,
            error_message="Circuit breaker OPEN",
        )
        return {
            "paid": False,
            "amount": 0.0,
            "reference": "",
            "message": "Billing service temporarily unavailable. Retry later.",
            "api_reachable": False,
        }

    t0 = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params={"plate": plate_number})
            resp.raise_for_status()
            data = resp.json()
            latency = round((time.perf_counter() - t0) * 1000, 1)

            _http_breaker.record_success()

            log.info(
                "Billing API response for plate %s: paid=%s ref=%s (%.1fms)",
                plate_number, data.get("paid"), data.get("reference"), latency,
            )

            result = {
                "paid": bool(data.get("paid", False)),
                "amount": float(data.get("amount", 0.0)),
                "reference": str(data.get("reference", "")),
                "message": str(data.get("message", "Payment status received")),
                "api_reachable": True,
            }

            _log_payment(
                plate_number=plate_number,
                api_url=url,
                request_payload=json.dumps({"plate": plate_number}),
                response_payload=json.dumps(data),
                status_code=resp.status_code,
                latency_ms=latency,
            )

            return result

    except httpx.HTTPStatusError as e:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        _http_breaker.record_failure()
        log.warning(
            "Billing API returned HTTP %s for plate %s: %s",
            e.response.status_code, plate_number, e,
        )
        _log_payment(
            plate_number=plate_number,
            api_url=url,
            status_code=e.response.status_code,
            latency_ms=latency,
            error_message=str(e),
        )
        return {
            "paid": False,
            "amount": 0.0,
            "reference": "",
            "message": f"Billing API error: HTTP {e.response.status_code}",
            "api_reachable": True,
        }

    except Exception as e:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        _http_breaker.record_failure()
        log.warning("Billing API unreachable for plate %s: %s", plate_number, e)
        _log_payment(
            plate_number=plate_number,
            api_url=url,
            latency_ms=latency,
            api_reachable=False,
            error_message=str(e),
        )
        return {
            "paid": False,
            "amount": 0.0,
            "reference": "",
            "message": "Billing API unreachable — vehicle cannot exit until payment is verified.",
            "api_reachable": False,
        }


# ---------------------------------------------------------------------------
# Mock Billing Backend (development/testing)
# ---------------------------------------------------------------------------

async def _check_payment_mock(plate_number: str) -> dict:
    """Always returns paid=True. For development and testing only."""
    log.info("MOCK billing: plate %s → paid=True", plate_number)
    return {
        "paid": True,
        "amount": 100.0,
        "reference": "MOCK-REF-001",
        "message": "Mock payment — always approved",
        "api_reachable": True,
    }


# ---------------------------------------------------------------------------
# Public API — dispatches to the configured backend
# ---------------------------------------------------------------------------

async def check_payment_status(plate_number: str) -> dict:
    """
    Query the configured billing backend to verify payment for a vehicle.

    The backend is selected via the BILLING_BACKEND setting:
      - "sap"  → SAPBillingClient
      - "http" → generic HTTP API (default)
      - "mock" → always returns paid=True

    Returns:
        {
            "paid": bool,
            "amount": float,
            "reference": str,
            "message": str,
            "api_reachable": bool,
        }
    """
    backend = settings.BILLING_BACKEND.lower()

    if backend == "sap":
        from backend.services.sap_client import SAPBillingClient
        client = SAPBillingClient()
        try:
            return await client.check_payment_status(plate_number)
        except Exception as e:
            log.error("SAP billing call failed for %s: %s", plate_number, e)
            return {
                "paid": False,
                "amount": 0.0,
                "reference": "",
                "message": f"SAP API error: {e}",
                "api_reachable": False,
            }

    elif backend == "mock":
        return await _check_payment_mock(plate_number)

    else:  # "http" — default
        return await _check_payment_http(plate_number)


async def sync_transaction(
    entry_id: int,
    plate_number: str,
    amount: float,
    reference: str = "",
) -> dict:
    """
    Push a completed transaction to the billing backend for reconciliation.
    Only meaningful for SAP backend; no-op for HTTP/mock.
    """
    backend = settings.BILLING_BACKEND.lower()

    if backend == "sap":
        from backend.services.sap_client import SAPBillingClient
        client = SAPBillingClient()
        try:
            return await client.sync_transaction(entry_id, plate_number, amount, reference)
        except Exception as e:
            log.error("SAP transaction sync failed: %s", e)
            return {"synced": False, "message": str(e)}

    else:
        log.debug("Transaction sync skipped — backend=%s", backend)
        return {"synced": False, "message": f"Sync not implemented for backend '{backend}'"}
