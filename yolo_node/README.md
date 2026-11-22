# yolo_node

**Real-Time Object Detection via YOLOv5**

## Purpose
Runs YOLOv5 inference on USB camera streams and publishes detections as ROS2 topics. Designed for Jetson edge deployment with CUDA acceleration.

## Files

- **`yolo_detector.py`**: Main ROS2 node
  - Captures frames from USB camera (default index 0)
  - Runs YOLOv5 inference (default: `yolov5s` small model for speed)
  - Publishes detections as JSON + annotated JPEG images
  - Configurable confidence threshold, FPS, device (CUDA/CPU)

- **`test_camera.py`**: Standalone camera test (no ROS2)
  - Verifies USB camera functionality
  - Run: `python3 test_camera.py` (opens OpenCV window)

- **`__init__.py`**: Package marker

## Topics

### Published
1. **`/detections`** (std_msgs/String)
   - JSON array of detected objects per frame
   - Format: `[{"class": "person", "confidence": 0.95, "bbox": [x, y, w, h]}, ...]`
   - Publish rate: configurable (default 5 Hz)

2. **`/camera/detection_image`** (sensor_msgs/CompressedImage)
   - Annotated JPEG with bounding boxes, labels, confidence
   - Publish rate: same as detections
   - Useful for RViz visualization or monitoring dashboard

## Parameters

| Param | Type | Default | Range |
|-------|------|---------|-------|
| `model_path` | str | `yolov5s` | `yolov5n/s/m/l/x` or path to `.pt` |
| `confidence` | float | 0.45 | 0.0–1.0 |
| `camera_index` | int | 0 | USB device ID |
| `publish_rate_hz` | float | 5.0 | 1–30 |
| `device` | str | auto (cuda/cpu) | `cuda`, `cpu`, `cuda:0` |

### Example Launch
```bash
ROS_DOMAIN_ID=28 python3 yolo_node/yolo_detector.py \
    --ros-args \
    -p model_path:=yolov5s \
    -p confidence:=0.5 \
    -p camera_index:=0 \
    -p publish_rate_hz:=10.0
```

## Dependencies

- **torch** + **torchvision**: Deep learning framework (CUDA-enabled)
- **yolov5**: Ultralytics detection model (auto-downloads on first run)
- **opencv-python** (cv2): Camera capture + image annotation
- **rclpy**: ROS2 Python client
- **sensor_msgs**, **std_msgs**: ROS2 message types

### Environment
```bash
# Create Python venv with CUDA support
python3.9 -m venv yolov5_env
source yolov5_env/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install yolov5 opencv-python rclpy sensor_msgs std-msgs-py
```

## Hardware Integration

### Camera Setup
- **USB Camera Index 0** (front-facing, typical)
- Frame size: VGA (640×480) or auto-detected
- Format: OpenCV BGR (converted to RGB for YOLO)

### GPU Acceleration
- **Jetson Jetpack** includes CUDA 11.x + cuDNN
- **torch** compiled for Arm64 + CUDA (via wheel)
- **Inference speed**: ~100-200 ms/frame (yolov5s on Jetson Orin)

## ROS2 Integration

### Systemd Service (manual)
```ini
[Unit]
Description=YOLO Detection Node
After=network.target

[Service]
Type=simple
User=jetson
WorkingDirectory=/home/jetson/clawbot
Environment="ROS_DOMAIN_ID=28"
ExecStart=/home/jetson/yolov5_env/bin/python3 yolo_node/yolo_detector.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Monitoring Dashboard Integration
- Monitoring app (port 5000) subscribes `/detections` → displays live objects
- `/camera/detection_image` streamed in dashboard

## Usage in Hardware Service

The main `hardware_service.py` (ros2_llm_bridge) doesn't directly control this node; however:
- **AnalyzeScene** tool: Can parse `/detections` topic to answer "what do you see?"
- **RecognizeObject** tool: Queries latest detection data

## Known Limitations

- **Latency**: 5–10 frames/sec inference → real-time tracking needs smoothing
- **Small Objects**: YOLOv5 struggles with objects <50px (gripper view); may need fine-tuning
- **Memory**: yolov5m/l models require >2GB VRAM (use `yolov5s` on Jetson Nano)
- **FPS Bottleneck**: USB camera + inference + ROS2 pub = ~5 Hz realistic on Orin

## Testing

### Check Detections in Real-Time
```bash
ROS_DOMAIN_ID=28 ros2 topic echo /detections
```

### Record Frame + Detections (ROS2 bag)
```bash
ros2 bag record /detections /camera/detection_image -o detection_run
```

## Future Work
- [ ] Fine-tune model on clawbot-specific objects (gripper targets, obstacles)
- [ ] Implement tracking (SORT/ByteTrack) for temporal consistency
- [ ] Multi-camera support (front + claw camera)
- [ ] Depth integration (with Astra Pro+ RGB-D)

**Status**: ✅ Operational. Verified on Jetson Orin (yolov5s @ 10 Hz).

**Maintainer**: clawbot developers
