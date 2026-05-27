"""
scripts/test_camera.py
~~~~~~~~~~~~~~~~~~~~~~~
Quick camera connection test utility.

Tests RTSP, webcam, or video file sources and reports:
  - Whether the source can be opened
  - Resolution, FPS, codec
  - Captures and saves a test frame

Usage:
    python scripts/test_camera.py                     # Test webcam 0
    python scripts/test_camera.py rtsp://ip/stream    # Test RTSP
    python scripts/test_camera.py sample.mp4          # Test video file
"""

import sys
import os
import time
import cv2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)


def test_camera(source):
    """Test a camera/video source and report status."""
    print("=" * 60)
    print("  ANPR.OS — Camera Connection Test")
    print("=" * 60)
    print(f"  Source: {source}")
    print()

    # Try to open
    print("Attempting to connect...")
    t0 = time.time()
    cap = cv2.VideoCapture(source)
    connect_time = time.time() - t0

    if not cap.isOpened():
        print(f"❌ FAILED to open source: {source}")
        print(f"   Connection attempt took: {connect_time:.2f}s")
        print()
        print("Troubleshooting:")
        print("  - For RTSP: Check URL format (rtsp://user:pass@ip:port/stream)")
        print("  - For webcam: Try index 0, 1, 2...")
        print("  - For video: Check file path exists")
        return False

    print(f"✅ Connected in {connect_time:.2f}s")
    print()

    # Get properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    codec_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = "".join([chr((codec_int >> (8 * i)) & 0xFF) for i in range(4)])
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print("Camera Properties:")
    print(f"  Resolution: {width}x{height}")
    print(f"  FPS:        {fps:.1f}")
    print(f"  Codec:      {codec}")
    if total_frames > 0:
        duration = total_frames / fps if fps > 0 else 0
        print(f"  Frames:     {total_frames}")
        print(f"  Duration:   {duration:.1f}s")
    print()

    # Capture test frame
    print("Reading test frame...")
    ret, frame = cap.read()
    if ret and frame is not None:
        print(f"✅ Frame captured: {frame.shape}")

        # Save test frame
        os.makedirs("tests", exist_ok=True)
        out_path = os.path.join("tests", "camera_test_frame.jpg")
        cv2.imwrite(out_path, frame)
        print(f"   Saved to: {out_path}")
    else:
        print("❌ Failed to read frame")

    # Measure actual FPS (10 frames)
    print()
    print("Measuring actual read speed (30 frames)...")
    t0 = time.time()
    count = 0
    for _ in range(30):
        ret, _ = cap.read()
        if ret:
            count += 1
    elapsed = time.time() - t0
    actual_fps = count / elapsed if elapsed > 0 else 0

    print(f"  Read {count}/30 frames in {elapsed:.2f}s")
    print(f"  Actual read speed: {actual_fps:.1f} FPS")

    cap.release()

    print()
    print("=" * 60)
    print("  Test Complete ✅")
    print("=" * 60)

    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        source = sys.argv[1]
        # Convert digit strings to int (webcam index)
        if source.isdigit():
            source = int(source)
    else:
        source = 0  # Default: webcam 0

    test_camera(source)
