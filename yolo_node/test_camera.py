#!/usr/bin/env python3
"""Camera availability test for Clawbot YOLO node.

Usage:
    python3 yolo_node/test_camera.py [camera_index]
"""
import sys
import cv2


def test_camera(index: int = 0) -> bool:
    """Test that a camera is accessible and returns frames.

    Args:
        index: OpenCV VideoCapture device index.

    Returns:
        True if camera is accessible and returns a valid frame.
    """
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"❌ FAIL — Camera {index} not accessible")
        return False
    for _ in range(3):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None or frame.size == 0:
        print(f"❌ FAIL — Camera {index} opened but returned empty frame")
        return False
    h, w = frame.shape[:2]
    print(f"✅ OK — Camera {index}: {w}x{h} frame captured")
    return True


if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    sys.exit(0 if test_camera(idx) else 1)
