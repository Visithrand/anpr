"""
ocr_worker/ocr_engine.py
~~~~~~~~~~~~~~~~~~~~~~~~
OCR client engine for the decoupled OCR worker.

Communicates with the PaddleOCR FastAPI microservice.
Implements best-of-N consensus reads for reliability.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from typing import List, Optional

import cv2
import numpy as np
import requests

from backend.config import settings
from backend.utils.helpers import normalize_plate

log = logging.getLogger(__name__)


def is_valid_plate(text: str) -> bool:
    """
    Validate plate number format.
    Must be alphanumeric, between 7 and 12 chars, and contain both letters and digits.
    Indian plates are typically 9-10 chars (e.g. DL7SCB4578), so 7 is a safe minimum
    that rejects fragments like 'DL7S' or 'CB4578'.
    """
    clean = normalize_plate(text)
    if not re.match(r'^[A-Z0-9]{7,12}$', clean):
        return False
    has_alpha = any(c.isalpha() for c in clean)
    has_digit = any(c.isdigit() for c in clean)
    return has_alpha and has_digit


def _brighten(img: np.ndarray, beta: int = 30) -> np.ndarray:
    """Increase brightness by adding a constant."""
    return cv2.convertScaleAbs(img, alpha=1.0, beta=beta)


def _sharpen(img: np.ndarray) -> np.ndarray:
    """Apply a sharpening kernel."""
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]], dtype=np.float32)
    return cv2.filter2D(img, -1, kernel)


class OCREngine:
    """
    Sends cropped plate images to the PaddleOCR API microservice.
    
    Uses best-of-3 consensus: sends the original crop + 2 augmented versions
    (brightened, sharpened) and picks the most common valid result.
    This eliminates random OCR noise that varies between reads.
    """

    def __init__(self):
        self.url = settings.OCR_SERVICE_URL
        self.timeout = settings.OCR_TIMEOUT_SECONDS

    def _send_single(self, crop: np.ndarray) -> str:
        """Send a single crop to the OCR service. Returns raw text or empty string."""
        try:
            _, buf = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
            file_data = {"file": ("plate.jpg", buf.tobytes(), "image/jpeg")}
            resp = requests.post(self.url, files=file_data, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json().get("text", "")
        except requests.RequestException as e:
            log.debug("OCR request failed: %s", e)
        return ""

    def read_plate(self, crop: np.ndarray, max_retries: int = 2) -> str:
        """
        Best-of-3 consensus OCR read.
        
        Sends the crop in 3 variants (original, brightened, sharpened) to the
        PaddleOCR service. Takes the most common valid result as the final answer.
        
        If consensus fails (all different), falls back to the first valid result.
        """
        if crop is None or crop.size == 0:
            return ""

        # Generate 3 variants of the crop
        variants = [
            crop,                    # Original
            _brighten(crop, 30),     # Brightened
            _sharpen(crop),          # Sharpened
        ]

        results: List[str] = []
        for variant in variants:
            text = self._send_single(variant)
            if text:
                normalized = normalize_plate(text)
                if is_valid_plate(normalized):
                    results.append(normalized)

        if not results:
            # All 3 failed — do a single retry with original
            for attempt in range(max_retries):
                text = self._send_single(crop)
                if text:
                    normalized = normalize_plate(text)
                    if is_valid_plate(normalized):
                        return normalized
                time.sleep(0.3 * (attempt + 1))
            return ""

        # Consensus: pick the most common result
        counter = Counter(results)
        best_text, best_count = counter.most_common(1)[0]
        
        if best_count >= 2:
            log.debug("OCR consensus (%d/3 agree): %s", best_count, best_text)
        else:
            log.debug("OCR no consensus, using first valid: %s (all results: %s)", 
                      best_text, results)

        return best_text
