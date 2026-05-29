"""
backend/utils/helpers.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Utility functions used across the application.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Indian State Codes (used for plate prefix validation / correction)
# ---------------------------------------------------------------------------
INDIAN_STATES = {
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "GA",
    "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH",
    "ML", "MN", "MP", "MZ", "NL", "OD", "PB", "PY", "RJ", "SK",
    "TN", "TR", "TS", "UK", "UP", "WB",
}


def clean_indian_plate(text: str) -> str:
    """
    Attempt to correct common OCR noise on Indian license plates.

    Handles:
      - Leading junk characters before a valid 2-letter state code
        (e.g. 'PDL7SCB4578' → 'DL7SCB4578')
      - Trailing junk after the plate number
        (e.g. 'DL7SCB4578X' → 'DL7SCB4578')
      - Both leading AND trailing noise simultaneously
    """
    if not text or len(text) < 7:
        return text

    # Primary approach: use regex to extract a valid Indian plate pattern
    # Format: [A-Z]{2} [0-9]{1,2} [A-Z]{0,3} [0-9]{1,4}
    # Examples: DL7SCB4578, KA01AB1234, MH12DE1433, TN10Z1234
    plate_pattern = re.compile(
        r'([A-Z]{2}'       # State code (2 letters)
        r'[0-9]{1,2}'      # District code (1-2 digits)
        r'[A-Z]{0,3}'      # Series letters (0-3 letters)
        r'[0-9]{1,4})'     # Registration number (1-4 digits)
    )

    match = plate_pattern.search(text)
    if match:
        extracted = match.group(1)
        # Verify the state code is a real Indian state
        state_code = extracted[:2]
        if state_code in INDIAN_STATES and len(extracted) >= 7:
            return extracted

    # Fallback: legacy offset-based approach for edge cases
    for offset in range(min(4, len(text) - 6)):
        candidate_state = text[offset:offset + 2]
        if candidate_state in INDIAN_STATES:
            corrected = text[offset:]
            if len(corrected) >= 7 and re.match(r'^[A-Z]{2}[0-9]', corrected):
                # Also trim trailing junk: keep only up to 12 chars
                # (longest Indian plates are ~10-11 chars)
                if len(corrected) > 12:
                    corrected = corrected[:12]
                return corrected
            break

    return text


def normalize_plate(text: str) -> str:
    """Normalize a plate number: strip whitespace, hyphens, uppercase, and clean OCR noise."""
    if not text:
        return ""
    cleaned = re.sub(r'[\s\-]', '', text).strip().upper()
    cleaned = clean_indian_plate(cleaned)
    return cleaned


def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"
    else:
        h, remainder = divmod(int(seconds), 3600)
        m, s = divmod(remainder, 60)
        return f"{h}h {m}m"


def get_disk_usage(path: str = ".") -> dict:
    """Return disk usage info for the given path."""
    try:
        usage = shutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / (1024 ** 3), 2),
            "used_gb": round(usage.used / (1024 ** 3), 2),
            "free_gb": round(usage.free / (1024 ** 3), 2),
            "percent_used": round((usage.used / usage.total) * 100, 1),
        }
    except Exception as e:
        log.warning("Failed to get disk usage for '%s': %s", path, e)
        return {"error": str(e)}


def cleanup_old_snapshots(snapshot_dir: str, retention_days: int = 30) -> int:
    """
    Delete snapshot images older than ``retention_days``.

    Returns the number of files deleted.
    """
    deleted = 0
    cutoff = time.time() - (retention_days * 86400)
    snapshot_path = Path(snapshot_dir)

    if not snapshot_path.exists():
        return 0

    for f in snapshot_path.iterdir():
        if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    deleted += 1
            except Exception as e:
                log.warning("Failed to delete old snapshot %s: %s", f.name, e)

    if deleted > 0:
        log.info(
            "Snapshot cleanup: deleted %d files older than %d days from %s",
            deleted, retention_days, snapshot_dir,
        )

    return deleted


def count_files_in_dir(directory: str) -> int:
    """Count the number of files in a directory."""
    try:
        return sum(1 for f in Path(directory).iterdir() if f.is_file())
    except Exception:
        return 0
