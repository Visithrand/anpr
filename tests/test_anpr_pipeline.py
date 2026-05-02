"""
tests/test_anpr_pipeline.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Quick offline smoke-test for the full ANPR pipeline.

Runs WITHOUT a live camera or a running FastAPI server.
Requires only:
  - backend/models/plate_det/openvino/best.xml  (exported model)
  - A test image  (set TEST_IMAGE below, or pass --image path/to/plate.jpg)

Usage
-----
  # from the repo root
  python -m pytest tests/test_anpr_pipeline.py -v

  # or run directly
  python tests/test_anpr_pipeline.py --image samples/plate.jpg
"""

import argparse
import sys
import time
import logging
from pathlib import Path

import cv2
import numpy as np

# ── Ensure repo root is on path when running directly ──────────────────────
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import OPENVINO_MODEL_PATH
from anpr.plate_detector import PlateDetector
from anpr.ocr import PlateOCR
from backend.services.anpr_service import ANPRService, ANPRResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("test_anpr")

# ── Default test image (a generated white rectangle = blank plate stand-in) ─
_FALLBACK_IMAGE = None   # will be generated below if no file given


def _make_synthetic_frame() -> np.ndarray:
    """800×300 grey frame with a white 'plate' rectangle in the centre."""
    frame = np.full((300, 800, 3), 80, dtype=np.uint8)
    cv2.rectangle(frame, (200, 80), (600, 220), (230, 230, 230), -1)
    cv2.putText(frame, "MH12AB1234", (220, 175),
                cv2.FONT_HERSHEY_SIMPLEX, 2.2, (20, 20, 20), 4)
    return frame


# ===========================================================================
# 1. Unit: PlateDetector
# ===========================================================================

def test_plate_detector_loads():
    model = Path(OPENVINO_MODEL_PATH)
    if not model.exists():
        log.warning("Model not found at %s — skipping detector load test.", model)
        return
    det = PlateDetector(model_xml=str(model))
    assert det is not None, "PlateDetector failed to instantiate"
    log.info("✓ PlateDetector loaded from %s", model)


def test_plate_detector_on_frame(frame: np.ndarray):
    model = Path(OPENVINO_MODEL_PATH)
    if not model.exists():
        log.warning("Model not found — skipping detector inference test.")
        return

    det = PlateDetector(model_xml=str(model))
    t0 = time.perf_counter()
    boxes = det.detect(frame)
    ms = (time.perf_counter() - t0) * 1000

    log.info("Detector inference: %.1f ms  |  boxes=%s", ms, boxes)
    assert isinstance(boxes, list), "detect() must return a list"
    assert len(boxes) <= 1, "PlateDetector must return at most 1 box"

    if boxes:
        x1, y1, x2, y2, score = boxes[0]
        assert 0.0 <= score <= 1.0, "Score out of [0,1] range"
        assert x1 < x2 and y1 < y2, "Invalid bounding box coords"
        crop = det.crop_plate(frame, boxes[0])
        assert crop.size > 0, "crop_plate returned empty array"
        log.info("✓ Best box: (%d,%d)→(%d,%d) conf=%.3f", x1, y1, x2, y2, score)
    else:
        log.info("ℹ No plate detected (expected on synthetic frame without a real model)")


# ===========================================================================
# 2. Unit: PlateOCR
# ===========================================================================

def test_ocr_on_synthetic():
    """PaddleOCR should at least return a string (even if wrong on a fake crop)."""
    ocr = PlateOCR()
    crop = np.full((60, 200, 3), 230, dtype=np.uint8)
    cv2.putText(crop, "MH12AB1234", (5, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (10, 10, 10), 2)

    t0 = time.perf_counter()
    text = ocr.read(crop)
    ms = (time.perf_counter() - t0) * 1000

    assert isinstance(text, str), "read() must return str"
    log.info("OCR (%.1f ms): %r", ms, text)
    log.info("✓ PlateOCR returned a string")


def test_ocr_empty_input():
    ocr = PlateOCR()
    assert ocr.read(None) == "", "None input must return empty string"
    assert ocr.read(np.array([])) == "", "Empty array must return empty string"
    log.info("✓ PlateOCR handles None / empty input gracefully")


# ===========================================================================
# 3. Integration: ANPRService.process_frame
# ===========================================================================

def test_service_process_frame(frame: np.ndarray):
    model = Path(OPENVINO_MODEL_PATH)
    if not model.exists():
        log.warning("Model not found — skipping ANPRService integration test.")
        return

    svc = ANPRService()
    t0 = time.perf_counter()
    result = svc.process_frame(frame)
    ms = (time.perf_counter() - t0) * 1000

    assert isinstance(result, ANPRResult), "process_frame must return ANPRResult"
    log.info("process_frame (%.1f ms): detected=%s  plate=%r  conf=%.3f",
             ms, result.detected, result.plate_text, result.confidence)

    if result.detected:
        # annotate and save to disk for visual inspection
        out = svc.annotate(frame.copy(), result)
        out_path = ROOT / "tests" / "output_annotated.jpg"
        cv2.imwrite(str(out_path), out)
        log.info("✓ Annotated frame saved → %s", out_path)
    else:
        log.info("ℹ No plate detected (acceptable on synthetic frame)")

    log.info("✓ ANPRService.process_frame completed without exception")


# ===========================================================================
# Runner
# ===========================================================================

def run_all(image_path: str | None = None):
    if image_path:
        p = Path(image_path)
        if not p.exists():
            log.error("Image not found: %s", p)
            sys.exit(1)
        frame = cv2.imread(str(p))
        if frame is None:
            log.error("cv2.imread failed for %s", p)
            sys.exit(1)
        log.info("Using image: %s  (%dx%d)", p, frame.shape[1], frame.shape[0])
    else:
        log.info("No image supplied — using synthetic frame.")
        frame = _make_synthetic_frame()

    print("\n" + "="*60)
    print("  ANPR PIPELINE SMOKE TEST")
    print("="*60)

    print("\n[1] PlateDetector — model load")
    test_plate_detector_loads()

    print("\n[2] PlateDetector — inference")
    test_plate_detector_on_frame(frame)

    print("\n[3] PlateOCR — synthetic crop")
    test_ocr_on_synthetic()

    print("\n[4] PlateOCR — edge-case inputs")
    test_ocr_empty_input()

    print("\n[5] ANPRService — full pipeline")
    test_service_process_frame(frame)

    print("\n" + "="*60)
    print("  ALL TESTS PASSED ✓")
    print("="*60 + "\n")


# ── pytest entry points ─────────────────────────────────────────────────────
def test_detector_loads():      test_plate_detector_loads()
def test_detector_inference():  test_plate_detector_on_frame(_make_synthetic_frame())
def test_ocr_synthetic():       test_ocr_on_synthetic()
def test_ocr_edge():            test_ocr_empty_input()
def test_full_pipeline():       test_service_process_frame(_make_synthetic_frame())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ANPR pipeline smoke test")
    parser.add_argument("--image", default=None,
                        help="Path to a real plate image (optional)")
    args = parser.parse_args()
    run_all(args.image)
