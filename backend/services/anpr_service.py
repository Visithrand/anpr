"""
backend/services/anpr_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Central ANPR service that wires together:
  - PlateDetector  (OpenVINO YOLOv8 inference)
  - PlateOCR       (PaddleOCR with CLAHE preprocessing)

Public API
----------
ANPRService.process_frame(frame)  -> ANPRResult
ANPRService.trigger_entry(plate)  -> dict   (calls /entry internally)
ANPRService.trigger_exit(plate)   -> dict   (calls /exit  internally)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from backend.config import OPENVINO_MODEL_PATH
from anpr.plate_detector import PlateDetector
from anpr.ocr import PlateOCR

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ANPRResult:
    plate_text: str = ""
    confidence: float = 0.0
    box: Optional[tuple] = None          # (x1, y1, x2, y2, score)
    crop: Optional[np.ndarray] = None    # plate ROI as BGR array
    detected: bool = field(init=False)

    def __post_init__(self):
        self.detected = bool(self.plate_text)


# ---------------------------------------------------------------------------
# Service (singleton-friendly – instantiate once and reuse)
# ---------------------------------------------------------------------------

class ANPRService:
    """
    Usage
    -----
    svc = ANPRService()

    # from a camera frame
    result = svc.process_frame(frame)
    if result.detected:
        print(result.plate_text, result.confidence)

    # fire entry / exit against the FastAPI backend
    resp = await svc.trigger_entry(result.plate_text)
    """

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

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    def process_frame(self, frame: np.ndarray) -> ANPRResult:
        """
        Run the full ANPR pipeline on a single BGR frame.

        Returns
        -------
        ANPRResult
            .detected    – True if a plate was found and read
            .plate_text  – cleaned, uppercase plate string
            .confidence  – detector confidence score
            .box         – (x1, y1, x2, y2, score) in original-frame coords
            .crop        – BGR plate crop (None if no detection)
        """
        if frame is None or frame.size == 0:
            log.warning("process_frame received empty frame.")
            return ANPRResult()

        boxes = self._detector.detect(frame)
        if not boxes:
            return ANPRResult()

        best_box = boxes[0]                          # top-1 from PlateDetector
        crop = self._detector.crop_plate(frame, best_box)

        plate_text = self._ocr.read(crop)
        confidence = float(best_box[4])

        log.debug("Detected plate=%r  conf=%.3f", plate_text, confidence)

        return ANPRResult(
            plate_text=plate_text,
            confidence=confidence,
            box=best_box,
            crop=crop,
        )

    # ------------------------------------------------------------------
    # Optional: draw overlay onto the frame (in-place)
    # ------------------------------------------------------------------

    @staticmethod
    def annotate(frame: np.ndarray, result: ANPRResult) -> np.ndarray:
        """Draw bounding box + plate text onto *frame* (modifies in place)."""
        if not result.detected or result.box is None:
            return frame

        x1, y1, x2, y2, _ = result.box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        label = f"{result.plate_text}  {result.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), (0, 255, 0), -1)
        cv2.putText(
            frame, label,
            (x1 + 2, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
            (0, 0, 0), 2,
        )
        return frame

    # ------------------------------------------------------------------
    # Backend triggers (async – use inside FastAPI route handlers)
    # ------------------------------------------------------------------

    async def trigger_entry(self, plate: str, operator: str = "ANPR-System") -> dict:
        """POST /entry for *plate* and return the JSON response."""
        return await self._post("/entry", plate=plate, operator=operator)

    async def trigger_exit(self, plate: str, operator: str = "ANPR-System") -> dict:
        """POST /exit for *plate* and return the JSON response."""
        return await self._post("/exit", plate=plate, operator=operator)

    async def _post(self, path: str, **params) -> dict:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._base_url}{path}",
                    params=params,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            log.error("ANPRService._post(%s) failed: %s", path, exc)
            return {"error": str(exc)}
