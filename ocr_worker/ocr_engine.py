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
    
    Uses best-of-4 consensus: sends the original crop + 3 augmented versions
    (brightened, sharpened, high-contrast) and picks the most common valid result.
    Requires at least 2 agreeing reads (exact or fuzzy) to accept a result.
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

    @staticmethod
    def _plate_similarity(a: str, b: str) -> float:
        """Character-level LCS similarity between two plate strings (0.0–1.0)."""
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        n, m = len(a), len(b)
        if abs(n - m) / max(n, m) > 0.4:
            return 0.0
        dp = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        lcs_len = dp[n][m]
        return (2.0 * lcs_len) / (n + m)

    def _find_best_consensus(self, results: List[str]) -> str:
        """
        Find the best consensus result from a list of OCR reads.

        1. Exact match: if 2+ reads are identical, return that text.
        2. Fuzzy match: if 2+ reads are >=80% similar, pick the longest
           (most complete) one from the matching group.
        3. No consensus: return empty string (reject the read).
        """
        if not results:
            return ""

        # 1. Try exact consensus
        counter = Counter(results)
        best_text, best_count = counter.most_common(1)[0]
        if best_count >= 2:
            log.debug("OCR exact consensus (%d/%d agree): %s", best_count, len(results), best_text)
            return best_text

        # 2. Try fuzzy consensus — group reads that are >=80% similar
        FUZZY_THRESHOLD = 0.80
        for i in range(len(results)):
            group = [results[i]]
            for j in range(len(results)):
                if i == j:
                    continue
                if self._plate_similarity(results[i], results[j]) >= FUZZY_THRESHOLD:
                    group.append(results[j])

            if len(group) >= 2:
                # Pick the longest result in the group (most complete plate)
                best = max(group, key=len)
                log.debug(
                    "OCR fuzzy consensus (%d/%d similar): %s (group: %s)",
                    len(group), len(results), best, group,
                )
                return best

        # 3. No consensus — reject entirely
        log.debug("OCR no consensus, rejecting. All results: %s", results)
        return ""

    def read_plate(self, crop: np.ndarray, max_retries: int = 1) -> str:
        """
        Best-of-4 consensus OCR read.
        
        Sends the crop in 4 variants (original, brightened, sharpened,
        high-contrast grayscale) to the PaddleOCR service.
        
        Requires at least 2 reads to agree (exact or fuzzy) before
        accepting a result. If no pair agrees, returns empty string.
        """
        if crop is None or crop.size == 0:
            return ""

        # Generate a high-contrast grayscale variant
        def _high_contrast(img: np.ndarray) -> np.ndarray:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
            enhanced = clahe.apply(gray)
            return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

        # Generate 4 variants of the crop
        variants = [
            crop,                    # Original
            _brighten(crop, 30),     # Brightened
            _sharpen(crop),          # Sharpened
            _high_contrast(crop),    # High-contrast grayscale
        ]

        results: List[str] = []
        for variant in variants:
            text = self._send_single(variant)
            if text:
                normalized = normalize_plate(text)
                if is_valid_plate(normalized):
                    results.append(normalized)

        if not results:
            # All 4 failed — do a single retry with original
            for attempt in range(max_retries):
                text = self._send_single(crop)
                if text:
                    normalized = normalize_plate(text)
                    if is_valid_plate(normalized):
                        results.append(normalized)
                        break
                time.sleep(0.3 * (attempt + 1))

        if not results:
            return ""

        # If only 1 result came back, we can't establish consensus — reject
        if len(results) == 1:
            log.debug("OCR only 1 valid read ('%s'), no consensus possible — rejecting.", results[0])
            return ""

        return self._find_best_consensus(results)
