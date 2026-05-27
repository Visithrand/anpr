"""
backend/services/sap_client.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SAP Billing API integration client.

Provides a clean adapter for communicating with SAP's billing system.
Designed to be swapped in/out via the BILLING_BACKEND config.

Features:
  - check_payment_status(plate_number) → queries SAP for payment status
  - sync_transaction(entry_id, plate, amount) → pushes transaction to SAP
  - Retry with exponential backoff (via async_retry decorator)
  - Circuit breaker (auto-stops calling SAP after N consecutive failures)
  - Full request/response logging to PaymentLog table
  - Configurable auth (API key or OAuth)
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

# Circuit breaker — shared across all SAP calls
_sap_breaker = CircuitBreaker(
    failure_threshold=settings.BILLING_CIRCUIT_BREAKER_THRESHOLD,
    cooldown_seconds=settings.BILLING_CIRCUIT_BREAKER_COOLDOWN,
    name="sap_billing",
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


class SAPBillingClient:
    """
    SAP-specific billing integration.

    Expects SAP endpoints:
      GET  {SAP_API_URL}/payment/status?plate={plate_number}
      POST {SAP_API_URL}/transaction/sync
    """

    def __init__(self):
        self.base_url = settings.SAP_API_URL.rstrip("/") if settings.SAP_API_URL else ""
        self.api_key = settings.SAP_API_KEY
        self.timeout = settings.SAP_TIMEOUT
        self.breaker = _sap_breaker

    def _headers(self) -> dict:
        """Build auth headers for SAP API calls."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if settings.SAP_CLIENT_ID:
            headers["X-Client-ID"] = settings.SAP_CLIENT_ID
        return headers

    @async_retry(
        max_attempts=3,
        base_delay=1.0,
        backoff_multiplier=2.0,
        retry_on=(httpx.HTTPError, httpx.TimeoutException),
    )
    async def check_payment_status(self, plate_number: str) -> dict:
        """
        Query SAP for payment status of a vehicle.

        Returns:
            {
                "paid": bool,
                "amount": float,
                "reference": str,
                "message": str,
                "api_reachable": bool,
            }
        """
        if not self.base_url:
            log.warning("SAP_API_URL not configured — returning unpaid")
            return {
                "paid": False,
                "amount": 0.0,
                "reference": "",
                "message": "SAP API URL not configured",
                "api_reachable": False,
            }

        # Circuit breaker check
        if not self.breaker.can_execute():
            log.warning(
                "SAP circuit breaker OPEN — skipping API call for plate %s",
                plate_number,
            )
            _log_payment(
                plate_number=plate_number,
                api_url=f"{self.base_url}/payment/status",
                api_reachable=False,
                error_message="Circuit breaker OPEN — call skipped",
            )
            return {
                "paid": False,
                "amount": 0.0,
                "reference": "",
                "message": "Billing service temporarily unavailable (circuit breaker open). Retry later.",
                "api_reachable": False,
            }

        url = f"{self.base_url}/payment/status"
        t0 = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    url,
                    params={"plate": plate_number},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                latency = round((time.perf_counter() - t0) * 1000, 1)

                self.breaker.record_success()

                result = {
                    "paid": bool(data.get("paid", False)),
                    "amount": float(data.get("amount", 0.0)),
                    "reference": str(data.get("reference", "")),
                    "message": str(data.get("message", "SAP payment status received")),
                    "api_reachable": True,
                }

                _log_payment(
                    plate_number=plate_number,
                    api_url=url,
                    request_payload=json.dumps({"plate": plate_number}),
                    response_payload=json.dumps(data),
                    status_code=resp.status_code,
                    latency_ms=latency,
                    api_reachable=True,
                )

                log.info(
                    "SAP payment check: plate=%s paid=%s amount=%.2f latency=%.1fms",
                    plate_number, result["paid"], result["amount"], latency,
                )
                return result

        except httpx.HTTPStatusError as e:
            latency = round((time.perf_counter() - t0) * 1000, 1)
            self.breaker.record_failure()
            _log_payment(
                plate_number=plate_number,
                api_url=url,
                status_code=e.response.status_code,
                latency_ms=latency,
                api_reachable=True,
                error_message=str(e),
            )
            raise

        except Exception as e:
            latency = round((time.perf_counter() - t0) * 1000, 1)
            self.breaker.record_failure()
            _log_payment(
                plate_number=plate_number,
                api_url=url,
                latency_ms=latency,
                api_reachable=False,
                error_message=str(e),
            )
            raise

    @async_retry(
        max_attempts=3,
        base_delay=1.0,
        backoff_multiplier=2.0,
        retry_on=(httpx.HTTPError, httpx.TimeoutException),
    )
    async def sync_transaction(
        self,
        entry_id: int,
        plate_number: str,
        amount: float,
        reference: str = "",
    ) -> dict:
        """
        Push a completed transaction to SAP for reconciliation.
        """
        if not self.base_url:
            log.warning("SAP_API_URL not configured — transaction sync skipped")
            return {"synced": False, "message": "SAP API URL not configured"}

        if not self.breaker.can_execute():
            log.warning("SAP circuit breaker OPEN — transaction sync skipped")
            return {"synced": False, "message": "Circuit breaker open"}

        url = f"{self.base_url}/transaction/sync"
        payload = {
            "entry_id": entry_id,
            "plate_number": plate_number,
            "amount": amount,
            "reference": reference,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                self.breaker.record_success()
                log.info("SAP transaction synced: plate=%s amount=%.2f", plate_number, amount)
                return {"synced": True, "response": resp.json()}

        except Exception as e:
            self.breaker.record_failure()
            log.error("SAP transaction sync failed: %s", e)
            raise

    @property
    def circuit_breaker_info(self) -> dict:
        """Return circuit breaker state for health endpoint."""
        return self.breaker.info
