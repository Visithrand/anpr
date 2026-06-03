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


# ---------------------------------------------------------------------------
# OCR Character Confusion Maps
# ---------------------------------------------------------------------------
# Visually similar characters that OCR engines frequently confuse.
# Used to correct misreads based on positional context (letter vs digit).

# Digit → possible letter substitutions (for positions that MUST be letters)
DIGIT_TO_LETTER = {
    '0': ['O', 'D', 'Q', 'B'],
    '1': ['I', 'L'],
    '2': ['Z'],
    '3': ['E'],
    '4': ['A'],
    '5': ['S'],
    '6': ['G', 'B'],
    '7': ['T'],
    '8': ['B'],
    '9': ['G', 'P', 'B'],
}

# Letter → possible digit substitutions (for positions that MUST be digits)
LETTER_TO_DIGIT = {
    'O': '0', 'D': '0', 'Q': '0',
    'I': '1', 'L': '1',
    'Z': '2',
    'E': '3',
    'A': '4',
    'S': '5',
    'G': '6',
    'T': '7',
    'B': '8',
    'P': '9',
}


def _fix_state_code_confusion(text: str) -> str:
    """
    Try to correct OCR-confused digits in the first 2 characters (state code).

    Indian plates always start with a 2-letter state code (PB, DL, MH, etc.).
    OCR often misreads B→8, D→0, S→5, etc.

    Example: 'P811CRO612' → tries P+B = 'PB' → valid state → 'PB11CRO612'
    """
    if not text or len(text) < 7:
        return text

    c0, c1 = text[0], text[1]
    rest = text[2:]

    # If both chars are already letters and form a valid state, no fix needed
    if c0.isalpha() and c1.isalpha() and (c0 + c1) in INDIAN_STATES:
        return text

    # Generate candidate replacements for positions 0 and 1
    candidates_0 = [c0] if c0.isalpha() else DIGIT_TO_LETTER.get(c0, [])
    candidates_1 = [c1] if c1.isalpha() else DIGIT_TO_LETTER.get(c1, [])

    # Also include the original letter if it IS a letter
    if c0.isalpha():
        candidates_0 = [c0]
    if c1.isalpha():
        candidates_1 = [c1]

    for ch0 in candidates_0:
        for ch1 in candidates_1:
            state = ch0 + ch1
            if state in INDIAN_STATES:
                corrected = state + rest
                log.debug("State code fix: '%s' → '%s' (state: %s)", text[:2], state, state)
                return corrected

    return text


def _fix_digit_positions(text: str) -> str:
    """
    Correct OCR-confused letters in positions that MUST be digits.

    Indian plate format: SS DD [SSS] DDDD
      - Positions 2-3: district code (must be digits)
      - Last 1-4 chars: registration number (must be digits)

    Example: 'PB1ICRO6I2' → 'PB11CRO612' (I→1 in digit positions)
    """
    if not text or len(text) < 7:
        return text

    chars = list(text)

    # Fix district code (positions 2 and 3) — must be digits
    for pos in [2, 3]:
        if pos < len(chars) and chars[pos].isalpha():
            replacement = LETTER_TO_DIGIT.get(chars[pos])
            if replacement:
                log.debug("Digit fix pos %d: '%s' → '%s'", pos, chars[pos], replacement)
                chars[pos] = replacement

    # Fix trailing registration number — only fix letters embedded in the
    # final digit group (last 4 chars).  We scan from the end and stop as
    # soon as we hit a letter that ISN'T surrounded on BOTH sides by digits,
    # because that likely marks the boundary between series letters and the
    # registration number.
    i = len(chars) - 1
    end_limit = max(4, len(chars) - 4)  # Only touch the last 4 chars
    while i >= end_limit:
        if chars[i].isdigit():
            i -= 1
            continue
        elif chars[i].isalpha() and LETTER_TO_DIGIT.get(chars[i]):
            # Require BOTH neighbors to be digits — strict context check
            left_is_digit = (i - 1 >= 0 and chars[i - 1].isdigit())
            right_is_digit = (i + 1 < len(chars) and chars[i + 1].isdigit())
            if left_is_digit and right_is_digit:
                log.debug("Digit fix pos %d: '%s' → '%s'", i, chars[i], LETTER_TO_DIGIT[chars[i]])
                chars[i] = LETTER_TO_DIGIT[chars[i]]
                i -= 1
                continue
        break

    return ''.join(chars)


def clean_indian_plate(text: str) -> str:
    """
    Attempt to correct common OCR noise on Indian license plates.

    Handles:
      - OCR character confusions (B↔8, D↔0, S↔5, I↔1, etc.)
        using Indian state code validation to auto-correct
      - Leading junk characters before a valid 2-letter state code
        (e.g. 'PDL7SCB4578' → 'DL7SCB4578')
      - Trailing junk after the plate number
        (e.g. 'DL7SCB4578X' → 'DL7SCB4578')
      - Both leading AND trailing noise simultaneously
    """
    if not text or len(text) < 7:
        return text

    # Step 0: Fix OCR character confusions BEFORE regex matching
    # This corrects e.g. 'P811CRO612' → 'PB11CRO612'
    text = _fix_state_code_confusion(text)
    text = _fix_digit_positions(text)

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
