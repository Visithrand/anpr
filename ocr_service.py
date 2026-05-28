from fastapi import FastAPI, UploadFile, File
import cv2
import numpy as np
import logging
from paddleocr import PaddleOCR

# Reduce logs
logging.getLogger("ppocr").setLevel(logging.WARNING)

app = FastAPI(title="OCR Service")

# Initialize OCR model once
ocr = PaddleOCR(use_angle_cls=True, lang='en')


# -----------------------
# IMAGE PREPROCESSING
# -----------------------
def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Contrast enhancement
    clahe = cv2.createCLAHE(2.0, (8, 8))
    gray = clahe.apply(gray)

    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


# -----------------------
# OCR FUNCTION
# -----------------------
def extract_text(img):
    try:
        processed = preprocess(img)

        result = ocr.ocr(processed)

        if not result or not result[0]:
            return ""

        texts = [line[1][0] for line in result[0]]
        text = "".join(texts).replace(" ", "")

        return text.strip().upper()

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