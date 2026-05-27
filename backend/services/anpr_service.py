from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
import httpx

from backend.config import OPENVINO_MODEL_PATH
from anpr.plate_detector import PlateDetector
from anpr.ocr import PlateOCR

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RESULT
# ---------------------------------------------------------------------------

@dataclass
class ANPRResult:
    plate_text: str = ""
    confidence: float = 0.0
    box: Optional[tuple] = None
    crop: Optional[np.ndarray] = None
    detected: bool = field(init=False)

    def __post_init__(self):
        self.detected = (
            self.plate_text is not None
            and len(self.plate_text.strip()) >= 6
        )


# ---------------------------------------------------------------------------
# SERVICE
# ---------------------------------------------------------------------------

class ANPRService:

    def __init__(
        self,
        model_path: str = OPENVINO_MODEL_PATH,
        confidence: float = 0.5,
        base_url: str = "http://localhost:8000",
    ):
        log.info("Loading PlateDetector from %s …", model_path)
        self._detector = PlateDetector(model_xml=model_path, confidence=confidence)

        log.info("Initialising PaddleOCR …")
        self._ocr = PlateOCR()

        self._base_url = base_url.rstrip("/")
        log.info("ANPRService ready.")

    # ------------------------------------------------------
    # CORE PIPELINE
    # ------------------------------------------------------

    def process_frame(self, frame: np.ndarray) -> ANPRResult:
        if frame is None or frame.size == 0:
            return ANPRResult()

        boxes = self._detector.detect(frame)
        if not boxes:
            return ANPRResult()

        best_box = boxes[0]

        # crop FIRST (FIXED BUG)
        crop = self._detector.crop_plate(frame, best_box)

        # OCR
        plate_text = self._ocr.read(crop)
        confidence = float(best_box[4])

        # confidence filter
        if confidence < 0.5:
            return ANPRResult()

        return ANPRResult(
            plate_text=plate_text,
            confidence=confidence,
            box=best_box,
            crop=crop,
        )

    # ------------------------------------------------------
    # DRAW BOX
    # ------------------------------------------------------

    @staticmethod
    def annotate(frame: np.ndarray, result: ANPRResult) -> np.ndarray:
        if not result.detected or result.box is None:
            return frame

        x1, y1, x2, y2, _ = result.box

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        label = f"{result.plate_text} {result.confidence:.2f}"

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)

        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), (0, 255, 0), -1)

        cv2.putText(
            frame,
            label,
            (x1 + 2, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            2,
        )

        return frame

    # ------------------------------------------------------
    # BACKEND CALLS
    # ------------------------------------------------------

    async def trigger_entry(self, plate: str, operator: str = "ANPR-System") -> dict:
        return await self._post("/entry", plate=plate, operator=operator)

    async def trigger_exit(self, plate: str, operator: str = "ANPR-System") -> dict:
        return await self._post("/exit", plate=plate, operator=operator)

    async def _post(self, path: str, **params) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._base_url}{path}",
                    params=params,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            log.error("API call failed %s: %s", path, exc)
            return {"error": str(exc)}