"""
ocr_worker/detector.py
~~~~~~~~~~~~~~~~~~~~~~~
Wrapper around the OpenVINO PlateDetector for the OCR worker.
"""

from __future__ import annotations

import logging
import numpy as np
from typing import List, Tuple

from backend.config import settings
from anpr.plate_detector import PlateDetector

log = logging.getLogger(__name__)


class DetectorWrapper:
    """
    Wraps the PlateDetector model.
    """

    def __init__(self):
        log.info("Loading OpenVINO PlateDetector model: %s", settings.OPENVINO_MODEL_PATH)
        self.detector = PlateDetector(
            settings.OPENVINO_MODEL_PATH,
            confidence=settings.PLATE_CONFIDENCE_THRESHOLD,
        )

    def detect_plates(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """
        Run inference to detect plate boxes.
        Returns a list of (x1, y1, x2, y2, confidence).
        """
        return self.detector.detect(frame)

    def crop_plate(self, frame: np.ndarray, box: Tuple[int, int, int, int, float], margin: int = 15) -> np.ndarray:
        """
        Crop plate from frame with margin.
        """
        return self.detector.crop_plate(frame, box, margin)
