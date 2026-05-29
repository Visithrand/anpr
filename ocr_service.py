from fastapi import FastAPI, UploadFile, File
import cv2
import numpy as np
import logging
import re
from paddleocr import PaddleOCR

# Reduce logs
logging.getLogger("ppocr").setLevel(logging.WARNING)

app = FastAPI(title="OCR Service")

# Initialize OCR model once
# IMPORTANT: use_angle_cls=False — ANPR plates are always roughly horizontal.
# Angle classification causes false rotations that misread characters.
ocr = PaddleOCR(use_angle_cls=False, lang='en', show_log=False)


# -----------------------
# IMAGE PREPROCESSING
# -----------------------
def remove_border(img, border_pct=0.05):
    """
    Remove a percentage of pixels from each edge of the image.
    
    License plate crops often include frame/border artifacts at the edges
    that PaddleOCR misreads as characters (e.g., a dark border becomes 'P').
    Trimming 5% from each side eliminates this noise.
    """
    h, w = img.shape[:2]
    top = int(h * border_pct)
    bottom = h - int(h * border_pct)
    left = int(w * border_pct)
    right = w - int(w * border_pct)
    
    # Ensure we don't crop too aggressively on tiny images
    if bottom - top < 10 or right - left < 20:
        return img
    
    return img[top:bottom, left:right]


def preprocess(img):
    """
    Multi-stage preprocessing pipeline for license plate OCR.
    
    Steps:
    1. Remove border artifacts (edges that get misread as junk chars)
    2. Resize to a standard height for consistent OCR
    3. Convert to grayscale
    4. CLAHE contrast enhancement
    5. Bilateral filter to reduce noise while keeping edges
    6. Adaptive thresholding for clean binary text
    """
    # Step 1: Remove border artifacts
    img = remove_border(img, border_pct=0.06)
    
    # Step 2: Resize to standard height (64px) maintaining aspect ratio
    # This gives PaddleOCR a consistent input size
    h, w = img.shape[:2]
    if h > 0:
        target_h = 64
        scale = target_h / h
        new_w = max(int(w * scale), 1)
        img = cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_CUBIC)
    
    # Step 3: Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 4: CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    gray = clahe.apply(gray)

    # Step 5: Bilateral filter — smooths noise, preserves character edges
    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    # Step 6: Adaptive threshold — creates clean black text on white background
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10
    )

    # Convert back to BGR for PaddleOCR (it expects 3-channel input)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


# -----------------------
# POST-OCR TEXT CLEANING
# -----------------------
def clean_ocr_text(text: str) -> str:
    """
    Clean raw PaddleOCR output to extract only valid plate characters.
    
    Handles:
    - Strips all non-alphanumeric characters (spaces, dashes, dots, etc.)
    - Removes common OCR misread characters at edges
    - Tries to extract an Indian plate pattern if possible
    """
    if not text:
        return ""
    
    # Strip everything except A-Z and 0-9
    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    if not cleaned:
        return ""
    
    # Try to extract Indian plate pattern:
    # Format: SS DD [S{0,3}] DDDD  (e.g., DL 7S CB 4578 or KA 01 AB 1234)
    # Where S=letter, D=digit
    # This regex captures the most common Indian plate formats
    indian_pattern = re.compile(
        r'([A-Z]{2}'       # State code: 2 letters
        r'[0-9]{1,2}'      # District code: 1-2 digits
        r'[A-Z]{0,3}'      # Series: 0-3 letters
        r'[0-9]{1,4})'     # Number: 1-4 digits
    )
    
    match = indian_pattern.search(cleaned)
    if match:
        extracted = match.group(1)
        # Only use extracted if it's reasonably long (7+ chars = valid plate)
        if len(extracted) >= 7:
            return extracted
    
    # Fallback: return cleaned text if no pattern match
    return cleaned


# -----------------------
# OCR FUNCTION
# -----------------------
def extract_text(img):
    try:
        processed = preprocess(img)

        result = ocr.ocr(processed, cls=False)

        if not result or not result[0]:
            return ""

        texts = [line[1][0] for line in result[0]]
        text = "".join(texts).replace(" ", "")
        
        raw_text = text.strip().upper()
        
        # Apply post-OCR cleaning
        cleaned = clean_ocr_text(raw_text)
        
        return cleaned

    except Exception as e:
        print("OCR error:", e)
        return ""


# -----------------------
# ROUTES
# -----------------------
@app.get("/")
def root():
    return {"message": "OCR Service Running 🚀"}


@app.post("/ocr")
async def run_ocr(file: UploadFile = File(...)):
    contents = await file.read()

    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return {"text": "", "error": "Invalid image"}

    text = extract_text(img)

    return {"text": text}