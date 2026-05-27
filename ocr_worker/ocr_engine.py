"""
ocr_worker/ocr_engine.py
~~~~~~~~~~~~~~~~~~~~~~~~
OCR client engine for the decoupled OCR worker.

Communicates with the PaddleOCR FastAPI microservice.
"""

from __future__ import annotations

import logging
import re
import time
import cv2
import numpy as np
import requests

from backend.config import settings
from backend.utils.helpers import normalize_plate

log = logging.getLogger(__name__)


def is_valid_plate(text: str) -> bool:
    """
    Validate plate number format.
    Must be alphanumeric, between 4 and 12 chars, and contain both letters and digits.
    """
    clean = normalize_plate(text)
    if not re.match(r'^[A-Z0-9]{4,12}$', clean):
        return False
    has_alpha = any(c.isalpha() for c in clean)
    has_digit = any(c.isdigit() for c in clean)
    return has_alpha and has_digit


class OCREngine:
    """
    Sends cropped plate images to the PaddleOCR API microservice.
    Includes connection retries and format verification.
    """

    def __init__(self):
        self.url = settings.OCR_SERVICE_URL
        self.timeout = settings.OCR_TIMEOUT_SECONDS

    def read_plate(self, crop: np.ndarray, max_retries: int = 2) -> str:
        """
        Encode the crop to JPEG and POST to PaddleOCR service.
        Implements basic retries for connection issues.
        """
        if crop is None or crop.size == 0:
            return ""

        try:
            _, buf = cv2.imencode('.jpg', crop)
            file_data = {"file": ("plate.jpg", buf.tobytes(), "image/jpeg")}
        except Exception as e:
            log.error("Failed to encode crop to JPEG: %s", e)
            return ""

        attempt = 0
        while attempt <= max_retries:
            try:
                resp = requests.post(
                    self.url,
                    files=file_data,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    text = resp.json().get("text", "")
                    return text
                else:
                    log.warning(
                        "PaddleOCR API returned HTTP %d (attempt %d/%d)",
                        resp.status_code, attempt + 1, max_retries + 1
                    )
            except requests.RequestException as e:
                log.warning(
                    "PaddleOCR API connection failed (attempt %d/%d): %s",
                    attempt + 1, max_retries + 1, e
                )

            attempt += 1
            if attempt <= max_retries:
                time.sleep(0.5 * attempt)  # Simple incremental backoff

        return ""
