#!/usr/bin/env python3
"""
Clawbot YOLO Inference Service — Local GPU inference for claw camera.

Runs YOLOv5s on CUDA and exposes a REST API for:
  - GET /detect?camera=claw|front  → capture + detect + return base64 annotated image + JSON
  - GET /detect_raw?camera=claw|front  → capture + detect + return JSON only (no image)
  - GET /health  → model status
  - GET /model  → model info (classes, device, conf threshold)

The service loads the model once at startup and keeps it in GPU memory.
Frame source per camera, choisie par CAMERA_<NOM>_SOURCE :
  - "ros"     : abonnement au topic ROS 2 publié par le nœud caméra (un seul propriétaire du
                périphérique — c'est le mode de la caméra du poignet, tenue par
                clawbot-wrist-camera.service) ;
  - "opencv"  : VideoCapture sur l'index V4L2 (mode historique, conservé pour les caméras qui
                n'ont pas de nœud ROS).

Usage:
  /home/jetson/yolov5_env/bin/python3 /home/jetson/clawbot/yolo_service.py
  /home/jetson/yolov5_env/bin/python3 /home/jetson/clawbot/yolo_service.py --port 8003 --camera 0
"""

import argparse
import base64
import cv2
import json
import logging
import os
import sys
import time
import threading

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [yolo_service] %(levelname)s %(message)s")
logger = logging.getLogger("yolo_service")

# ── Globals ───────────────────────────────────────────────────────────────────

MODEL = None
MODEL_NAMES = {}
DEVICE = "cuda"
CONF_THRESHOLD = 0.45
CAMERA_DEVICES = {
    "front": int(os.getenv("CAMERA_FRONT_INDEX", "0")),
    "claw":  int(os.getenv("CAMERA_CLAW_INDEX",  "2")),
}
CAMERA_SOURCES = {
    "front": os.getenv("CAMERA_FRONT_SOURCE", "opencv").lower(),
    "claw":  os.getenv("CAMERA_CLAW_SOURCE",  "opencv").lower(),
}
#: Topic ROS publié par le nœud caméra du poignet (clawbot-wrist-camera.service).
CAMERA_ROS_TOPICS = {
    "front": os.getenv("CAMERA_FRONT_ROS_TOPIC", "/wrist_camera/image_raw"),
    "claw":  os.getenv("CAMERA_CLAW_ROS_TOPIC",  "/wrist_camera/image_raw"),
}
#: Au-delà, on préfère une erreur explicite à une image vieille de plusieurs secondes.
ROS_FRAME_TIMEOUT_S = float(os.getenv("CAMERA_ROS_TIMEOUT_S", "2.0"))
DEFAULT_CAMERA = "claw"
MODEL_LOCK = threading.Lock()

# ── FastAPI ───────────────────────────────────────────────────────────────────

app = FastAPI(title="Clawbot YOLO Inference Service", version="1.0.0")

# ── Model loading ─────────────────────────────────────────────────────────────

def load_model(model_path: str):
    """Load YOLOv5 model via torch.hub."""
    global MODEL, MODEL_NAMES, DEVICE
    logger.info("Loading YOLOv5 model from %s on %s...", model_path, DEVICE)
    m = torch.hub.load(
        '/home/jetson/software/yolov5-7.0',
        'custom',
        path=model_path,
        source='local'
    )
    m.cuda()
    m.conf = CONF_THRESHOLD
    MODEL = m
    MODEL_NAMES = m.names
    logger.info("Model loaded: %d classes on %s", len(MODEL_NAMES), DEVICE)

# ── Capture + inference ───────────────────────────────────────────────────────

# ── Source ROS : un seul propriétaire du périphérique ─────────────────────────────
#
# Deux processus qui ouvrent /dev/video0 en V4L2 se volent le périphérique : le second échoue sur
# « Failed mapping device memory », sans que rien ne l'annonce côté appelant. La caméra du poignet
# appartient donc au nœud ROS (clawbot-wrist-camera.service) et ce service lit l'image par le
# topic. `rclpy` est importable depuis le venv yolov5 dès lors que /opt/ros/humble est sourcé
# (vérifié : python 3.10.12 dans les deux cas).

_ros = {"node": None, "frame": None, "stamp": 0.0, "erreur": None, "demarre": False}
_ros_lock = threading.Lock()


def _demarrer_source_ros() -> None:
    """Initialise rclpy et l'abonnement, une seule fois, dans un thread dédié."""
    with _ros_lock:
        if _ros["demarre"]:
            return
        _ros["demarre"] = True
    try:
        import rclpy
        from sensor_msgs.msg import Image

        rclpy.init(args=None)
        node = rclpy.create_node("yolo_source_camera")
        topics = set(CAMERA_ROS_TOPICS[s] for s in CAMERA_SOURCES if CAMERA_SOURCES[s] == "ros")

        def _garder(msg):
            try:
                image = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
            except Exception as exc:                     # encodage inattendu : on le dit
                _ros["erreur"] = f"image illisible ({msg.encoding}) : {exc}"
                return
            if msg.encoding == "yuv422_yuy2":
                # encodage natif de la caméra : la conversion est faite ici, une fois par image
                # demandée (le service interroge à 1-2 Hz), au lieu de l'être 15 fois par seconde
                # dans le nœud caméra où elle coûtait 60 ms par image.
                image = cv2.cvtColor(image, cv2.COLOR_YUV2BGR_YUYV)
            elif msg.encoding in ("rgb8", "bgr8"):
                if msg.encoding == "rgb8":
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            elif msg.encoding in ("mono8", "8UC1"):
                image = cv2.cvtColor(image[:, :, 0], cv2.COLOR_GRAY2BGR)
            else:
                _ros["erreur"] = f"encodage non gere : {msg.encoding}"
                return
            _ros["frame"] = image
            _ros["stamp"] = time.time()
            _ros["erreur"] = None

        for topic in topics:
            node.create_subscription(Image, topic, _garder, 2)
        _ros["node"] = node
        logger.info("source ROS active sur %s", ", ".join(sorted(topics)))
        threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    except Exception as exc:                             # noqa: BLE001 — on dégrade, on ne meurt pas
        _ros["erreur"] = f"source ROS indisponible : {type(exc).__name__}: {exc}"
        logger.error(_ros["erreur"])


def _image_ros(camera_name: str) -> np.ndarray:
    """Dernière image reçue sur le topic ROS de cette caméra, ou une erreur explicite."""
    _demarrer_source_ros()
    fin = time.time() + ROS_FRAME_TIMEOUT_S
    while time.time() < fin:
        frame = _ros["frame"]
        if frame is not None and time.time() - _ros["stamp"] < ROS_FRAME_TIMEOUT_S:
            return frame.copy()
        time.sleep(0.02)
    detail = _ros["erreur"] or f"aucune image sur {CAMERA_ROS_TOPICS[camera_name]}"
    raise RuntimeError(f"source ROS muette pour '{camera_name}' : {detail}")


def capture_frame(camera_name: str) -> np.ndarray:
    """Capture a single frame from the specified camera."""
    if camera_name not in CAMERA_DEVICES:
        raise ValueError(f"Unknown camera '{camera_name}'. Available: {list(CAMERA_DEVICES)}")
    if CAMERA_SOURCES.get(camera_name) == "ros":
        return _image_ros(camera_name)
    idx = CAMERA_DEVICES.get(camera_name)
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {camera_name} (index {idx})")
    for _ in range(3):
        cap.read()  # warm up
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError(f"Frame capture failed for camera {camera_name}")
    return frame

def run_inference(frame: np.ndarray) -> list:
    """Run YOLOv5 inference on a frame. Returns list of detections."""
    with MODEL_LOCK:
        t0 = time.time()
        results = MODEL(frame)
        t1 = time.time()
    det = results.xyxy[0].cpu().numpy()
    detections = []
    for d in det:
        cls = int(d[5])
        detections.append({
            "class": MODEL_NAMES.get(cls, str(cls)),
            "class_id": cls,
            "confidence": round(float(d[4]), 3),
            "bbox": {
                "x1": int(d[0]), "y1": int(d[1]),
                "x2": int(d[2]), "y2": int(d[3]),
            },
        })
    return detections, round((t1 - t0) * 1000)

def annotate_frame(frame: np.ndarray, detections: list) -> np.ndarray:
    """Draw bounding boxes on the frame."""
    annotated = frame.copy()
    colors = {
        "person": (0, 255, 0),
        "bottle": (0, 0, 255),
        "cup": (255, 0, 0),
    }
    for det in detections:
        x1, y1 = det["bbox"]["x1"], det["bbox"]["y1"]
        x2, y2 = det["bbox"]["x2"], det["bbox"]["y2"]
        cls = det["class"]
        conf = det["confidence"]
        color = colors.get(cls, (255, 255, 0))
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        label = f"{cls} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(annotated, (x1, y1 - th - 4), (x1 + tw, y1), color, -1)
        cv2.putText(annotated, label, (x1, y1 - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return annotated

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    model_path = os.getenv("YOLO_MODEL_PATH", "/home/jetson/software/yolov5-7.0/yolov5s.pt")
    load_model(model_path)

@app.get("/health")
async def health():
    return {
        "status": "ok" if MODEL is not None else "loading",
        "model_loaded": MODEL is not None,
        "device": DEVICE,
        "cameras": CAMERA_DEVICES,
        # la source est publiée : « la caméra ne répond pas » se diagnostique en lisant ce champ,
        # pas en devinant si le périphérique est occupé par un autre processus
        "sources": CAMERA_SOURCES,
        "ros_topics": {nom: topic for nom, topic in CAMERA_ROS_TOPICS.items()
                       if CAMERA_SOURCES.get(nom) == "ros"},
        "default_camera": DEFAULT_CAMERA,
    }

@app.get("/model")
async def model_info():
    if MODEL is None:
        raise HTTPException(503, "Model not loaded yet.")
    return {
        "model": os.path.basename(os.getenv("YOLO_MODEL_PATH", "yolov5s.pt")),
        "device": DEVICE,
        "confidence": CONF_THRESHOLD,
        "num_classes": len(MODEL_NAMES),
        "classes": list(MODEL_NAMES.values()),
    }

@app.post("/model")
async def switch_model(req: dict = None):
    """Switch YOLO model at runtime. Body: {"model_path": "/path/to/model.pt"}"""
    global MODEL, MODEL_NAMES
    try:
        body = req or {}
    except:
        body = {}
    model_path = body.get("model_path", "")
    if not model_path or not os.path.exists(model_path):
        raise HTTPException(400, f"Invalid model path: {model_path}")
    try:
        m = torch.hub.load(
            '/home/jetson/software/yolov5-7.0',
            'custom',
            path=model_path,
            source='local'
        )
        m.cuda()
        m.conf = CONF_THRESHOLD
        with MODEL_LOCK:
            MODEL = m
            MODEL_NAMES = m.names
        logger.info("Model switched to %s (%d classes)", model_path, len(m.names))
        return {
            "status": "ok",
            "model": os.path.basename(model_path),
            "num_classes": len(m.names),
            "classes": list(m.names.values()),
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to load model: {e}")

@app.get("/detect")
async def detect(
    camera: str = Query("claw", description="Camera: 'claw' or 'front'"),
    save: bool = Query(False, description="Save annotated image to disk"),
    annotate: bool = Query(True, description="Return base64 annotated image"),
):
    """Capture frame from camera, run YOLOv5 inference, return detections + annotated image."""
    if MODEL is None:
        raise HTTPException(503, "Model not loaded yet.")
    try:
        frame = capture_frame(camera)
    except Exception as e:
        raise HTTPException(500, f"Camera error: {e}")

    detections, inference_ms = run_inference(frame)

    result = {
        "camera": camera,
        "detections": detections,
        "detection_count": len(detections),
        "inference_ms": inference_ms,
        "frame_size": {"width": frame.shape[1], "height": frame.shape[0]},
    }

    if annotate:
        annotated = annotate_frame(frame, detections)
        _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        b64 = base64.b64encode(buf.tobytes()).decode()
        result["image_base64"] = b64
        result["format"] = "jpeg"

    if save:
        path = os.path.join(
            os.getenv("WORKSPACE_PATH", "/home/jetson/.openclaw/workspace"),
            f"yolo_{camera}.jpg"
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        annotated_img = annotate_frame(frame, detections) if not annotate else annotated
        cv2.imwrite(path, annotated_img)
        result["saved_path"] = path

    return result

@app.get("/detect_raw")
async def detect_raw(
    camera: str = Query("claw", description="Camera: 'claw' or 'front'"),
):
    """Capture + detect, return JSON only (no image base64). Lightweight."""
    if MODEL is None:
        raise HTTPException(503, "Model not loaded yet.")
    try:
        frame = capture_frame(camera)
    except Exception as e:
        raise HTTPException(500, f"Camera error: {e}")

    detections, inference_ms = run_inference(frame)

    return {
        "camera": camera,
        "detections": detections,
        "detection_count": len(detections),
        "inference_ms": inference_ms,
    }

@app.get("/stream")
async def stream(
    camera: str = Query("claw", description="Camera: 'claw' or 'front'"),
):
    """MJPEG stream with YOLOv5 detection overlay. Use in browser or <img src=...>"""
    from fastapi.responses import StreamingResponse
    import io

    def generate():
        source_ros = CAMERA_SOURCES.get(camera) == "ros"
        cap = None
        if not source_ros:
            idx = CAMERA_DEVICES.get(camera, 0)
            cap = cv2.VideoCapture(idx)
            if not cap.isOpened():
                return
        try:
            while True:
                if source_ros:
                    try:
                        frame = capture_frame(camera)
                    except RuntimeError as exc:
                        logger.warning("flux interrompu : %s", exc)
                        return
                else:
                    ret, frame = cap.read()
                    if not ret:
                        break
                with MODEL_LOCK:
                    results = MODEL(frame)
                det = results.xyxy[0].cpu().numpy()
                detections = []
                for d in det:
                    cls = int(d[5])
                    detections.append({
                        "class": MODEL_NAMES.get(cls, str(cls)),
                        "confidence": float(d[4]),
                        "bbox": [int(d[0]), int(d[1]), int(d[2]), int(d[3])]
                    })
                annotated = annotate_frame(frame, detections)
                _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
        finally:
            cap.release()

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clawbot YOLO Inference Service")
    parser.add_argument("--port", type=int, default=8003, help="HTTP port")
    parser.add_argument("--model", type=str, default="/home/jetson/software/yolov5-7.0/yolov5s.pt",
                        help="YOLOv5 model path")
    parser.add_argument("--conf", type=float, default=0.45, help="Confidence threshold")
    args = parser.parse_args()

    os.environ["YOLO_MODEL_PATH"] = args.model
    CONF_THRESHOLD = args.conf

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")