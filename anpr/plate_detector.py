import cv2
import numpy as np
from openvino import Core

class PlateDetector:
    def __init__(self, model_xml: str, confidence: float = 0.5):
        ie = Core()
        model = ie.read_model(model=model_xml)
        self.compiled = ie.compile_model(model=model, device_name="CPU")
        self.output = self.compiled.output(0)
        self.conf = confidence
        self.input_size = 640

    def detect(self, frame: np.ndarray):
        orig_h, orig_w = frame.shape[:2]
        blob = cv2.resize(frame, (self.input_size, self.input_size))
        blob = cv2.cvtColor(blob, cv2.COLOR_BGR2RGB)
        blob = blob.transpose(2, 0, 1)[np.newaxis].astype(np.float32) / 255.0
        result = self.compiled([blob])[self.output]
        boxes = self._parse(result, orig_w, orig_h)
        return boxes

    def _parse(self, result, orig_w, orig_h):
        pred = result[0].T  # [8400, 5]
        raw_boxes = []
        confidences = []
        for row in pred:
            x, y, w, h, score = row
            if score < self.conf:
                continue
            x1 = int((x - w / 2) * orig_w / self.input_size)
            y1 = int((y - h / 2) * orig_h / self.input_size)
            x2 = int((x + w / 2) * orig_w / self.input_size)
            y2 = int((y + h / 2) * orig_h / self.input_size)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(orig_w, x2), min(orig_h, y2)
            raw_boxes.append([x1, y1, x2 - x1, y2 - y1])  # [x, y, w, h] for NMS
            confidences.append(float(score))

        if not raw_boxes:
            return []

        # Apply OpenCV NMS to suppress overlapping detections of the same plate
        indices = cv2.dnn.NMSBoxes(raw_boxes, confidences, self.conf, 0.4)

        boxes = []
        for i in indices:
            idx = int(i[0]) if isinstance(i, (list, tuple, np.ndarray)) else int(i)
            bx, by, bw, bh = raw_boxes[idx]
            boxes.append((bx, by, bx + bw, by + bh, confidences[idx]))

        boxes.sort(key=lambda b: b[4], reverse=True)
        return boxes

    def crop_plate(self, frame: np.ndarray, box: tuple, margin: int = 0) -> np.ndarray:
        x1, y1, x2, y2, _ = box
        orig_h, orig_w = frame.shape[:2]
        
        # Add margin to the bounding box
        x1 = max(0, int(x1 - margin))
        y1 = max(0, int(y1 - margin))
        x2 = min(orig_w, int(x2 + margin))
        y2 = min(orig_h, int(y2 + margin))
        
        return frame[y1:y2, x1:x2]