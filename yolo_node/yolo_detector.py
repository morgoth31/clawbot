#!/usr/bin/env python3
"""YoloDetectorNode — ROS2 object detection node for Clawbot.

Captures frames from a USB camera, runs YOLOv5 inference, and publishes:
  - /detections     (std_msgs/String)           → JSON list of detections
  - /camera/detection_image (sensor_msgs/CompressedImage) → annotated JPEG

Usage (standalone):
    ROS_DOMAIN_ID=28 python3 yolo_node/yolo_detector.py

Usage (with params):
    ROS_DOMAIN_ID=28 python3 yolo_node/yolo_detector.py \\
        --ros-args -p model_path:=yolov5s -p confidence:=0.5 -p camera_index:=0
"""

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String


class YoloDetectorNode(Node):
    """ROS2 node that runs YOLOv5 inference on a USB camera stream.

    Publishes detection results as JSON strings and annotated compressed
    images at a configurable rate. Designed for the Clawbot X3 Jetson platform.

    Parameters:
        model_path (str): YOLOv5 model name ('yolov5s', 'yolov5m', etc.)
            or absolute path to a local .pt file. Default: 'yolov5s'.
        confidence (float): Minimum confidence threshold [0.0–1.0].
            Default: 0.45.
        camera_index (int): OpenCV VideoCapture device index.
            Default: 0 (front camera).
        publish_rate_hz (float): Detection and publish frequency in Hz.
            Default: 5.0.
        device (str): Torch device ('cuda', 'cpu', or 'cuda:0').
            Default: 'cuda' if available, else 'cpu'.
    """

    def __init__(self) -> None:
        """Initialize the YOLO detector node, load model, and start timer."""
        super().__init__("yolo_detector_node")

        # ── ROS2 parameters ────────────────────────────────────────────────
        self.declare_parameter("model_path",      "yolov5s")
        self.declare_parameter("confidence",      0.45)
        self.declare_parameter("camera_index",    0)
        self.declare_parameter("publish_rate_hz", 5.0)
        self.declare_parameter("device",          "")

        model_path      = self.get_parameter("model_path").value
        self.confidence = self.get_parameter("confidence").value
        self.cam_idx    = self.get_parameter("camera_index").value
        rate_hz         = self.get_parameter("publish_rate_hz").value
        device_param    = self.get_parameter("device").value

        # ── Device selection ───────────────────────────────────────────────
        import torch
        if device_param:
            self.device = device_param
        else:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # ── Load YOLOv5 model ──────────────────────────────────────────────
        self.model = self._load_model(model_path)

        # ── Publishers ─────────────────────────────────────────────────────
        qos = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._pub_detections = self.create_publisher(String, "/detections", qos)
        self._pub_image      = self.create_publisher(
            CompressedImage, "/camera/detection_image", qos
        )

        # ── Timer ──────────────────────────────────────────────────────────
        self._timer = self.create_timer(1.0 / rate_hz, self._detect_callback)

        self.get_logger().info(
            f"YoloDetectorNode ready — model={model_path} device={self.device} "
            f"camera={self.cam_idx} conf={self.confidence} rate={rate_hz}Hz"
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _load_model(self, model_path: str):
        """Load a YOLOv5 model from hub or local file.

        Args:
            model_path: Hub model name (e.g. 'yolov5s') or path to .pt file.

        Returns:
            Loaded YOLOv5 model ready for inference.

        Raises:
            RuntimeError: If model loading fails.
        """
        import torch
        try:
            if Path(model_path).exists():
                self.get_logger().info(f"Loading local model: {model_path}")
                model = torch.hub.load(
                    "ultralytics/yolov5", "custom",
                    path=model_path, verbose=False
                )
            else:
                self.get_logger().info(f"Loading hub model: {model_path}")
                model = torch.hub.load(
                    "ultralytics/yolov5", model_path,
                    pretrained=True, verbose=False
                )
            model.to(self.device)
            model.conf = self.confidence
            return model
        except Exception as exc:
            self.get_logger().error(f"Failed to load YOLO model: {exc}")
            raise RuntimeError(f"YOLO model load failed: {exc}") from exc

    def _capture_frame(self) -> np.ndarray | None:
        """Capture a single frame from the USB camera.

        Reads 3 warmup frames to flush the buffer before returning the live
        frame.

        Returns:
            BGR numpy array of shape (H, W, 3), or None on failure.
        """
        cap = cv2.VideoCapture(self.cam_idx)
        if not cap.isOpened():
            self.get_logger().warning(
                f"Camera index {self.cam_idx} not available — skipping frame"
            )
            return None
        try:
            for _ in range(3):          # flush buffer
                cap.read()
            ret, frame = cap.read()
            return frame if ret else None
        finally:
            cap.release()

    def _draw_detections(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Draw bounding boxes and labels on a frame copy.

        Args:
            frame: BGR image array.
            detections: List of detection dicts with keys
                label, confidence, bbox (x1,y1,x2,y2).

        Returns:
            Annotated BGR image array.
        """
        out = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            label = f"{det['label']} {det['confidence']:.2f}"
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                out, label, (x1, max(y1 - 8, 10)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2
            )
        return out

    # ── ROS2 timer callback ────────────────────────────────────────────────

    def _detect_callback(self) -> None:
        """Timer callback: capture → infer → publish detections + image.

        Runs YOLO inference on the latest camera frame and publishes:
          - /detections as a JSON string
          - /camera/detection_image as a JPEG-compressed annotated frame
        """
        frame = self._capture_frame()
        if frame is None:
            return

        # ── Run inference ──────────────────────────────────────────────────
        try:
            results = self.model(frame)
        except Exception as exc:
            self.get_logger().error(f"Inference error: {exc}")
            return

        # ── Parse results ──────────────────────────────────────────────────
        detections: list[dict] = []
        for *xyxy, conf, cls in results.xyxy[0].tolist():
            detections.append({
                "label":      results.names[int(cls)],
                "confidence": round(conf, 3),
                "bbox":       [round(v, 1) for v in xyxy],
            })

        # ── Publish detections JSON ────────────────────────────────────────
        msg_str = String()
        msg_str.data = json.dumps(detections)
        self._pub_detections.publish(msg_str)

        # ── Publish annotated image ────────────────────────────────────────
        annotated = self._draw_detections(frame, detections)
        _, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        msg_img              = CompressedImage()
        msg_img.header.stamp = self.get_clock().now().to_msg()
        msg_img.format       = "jpeg"
        msg_img.data         = jpeg.tobytes()
        self._pub_image.publish(msg_img)

        if detections:
            labels = [d["label"] for d in detections]
            self.get_logger().debug(f"Detected: {labels}")


def main() -> None:
    """Entry point — init ROS2 and spin the detector node."""
    rclpy.init()
    node = YoloDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
