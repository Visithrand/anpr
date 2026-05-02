import requests
import cv2


class PlateOCR:
    def __init__(self, url="http://127.0.0.1:8001/ocr"):
        self.url = url

    def read(self, plate_crop):
        if plate_crop is None or plate_crop.size == 0:
            return ""

        try:
            # Encode image
            _, buffer = cv2.imencode(".jpg", plate_crop)

            files = {
                "file": ("plate.jpg", buffer.tobytes(), "image/jpeg")
            }

            response = requests.post(self.url, files=files, timeout=5)

            if response.status_code != 200:
                return ""

            data = response.json()
            return data.get("text", "")

        except Exception as e:
            print("OCR error:", e)
            return ""