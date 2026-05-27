import cv2
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.services.anpr_service import ANPRService

logging.basicConfig(level=logging.INFO)

def run_video(video_path: str):
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(" Cannot open video:", video_path)
        return

    service = ANPRService()

    frame_count = 0
    import time
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        
        # Calculate and print FPS every 30 frames
        if frame_count % 30 == 0:
            elapsed = time.time() - start_time
            fps = 30 / elapsed
            print(f"⚡ Current Pipeline Speed: {fps:.2f} FPS")
            start_time = time.time()

        # Skip frames for performance (important for heavy traffic videos)
        if frame_count % 3 != 0:
            continue

        result = service.process_frame(frame)

        if result.detected:
            print(f" Plate Detected: {result.plate_text} | Conf: {result.confidence}")

            # optional: draw box
            frame = service.annotate(frame, result)

        cv2.imshow("ANPR LIVE", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    video_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample.mp4"))
    run_video(video_path)