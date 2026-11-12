---
type: Hardware
title: "Capteurs -- LiDAR, IMU, Cameras, Batterie"
description: Catalogue des capteurs du robot et leur integration ROS2.
status: stable
tags: [hardware, sensors, lidar, camera, imu]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:25:00Z
sources:
  - id: codebase-map
    resource: file:///home/jetson/clawbot/CODEBASE_MAP.md
    title: CODEBASE_MAP.md
    author: human:jetson
    last_modified: 2026-03-06
---

# Capteurs

## LiDAR
- **Model**: YDLIDAR (serie)
- **Driver**: ydlidar_ros2_driver_node
- **Usage**: SLAM (Cartographer), avoidance, warning
- **Topics**: /scan (LaserScan)
- **Safety**: LIDAR_SAFETY_REQUIRED=false (bypass actif)
- **Logs**: nombreux logs dans /home/jetson/.ros/log/

## IMU
- **Source**: Rosmaster_Lib (serial)
- **Topic**: /imu/data_raw (sensor_msgs/Imu)
- **Donnees**: accelerometre (x,y,z) + gyroscope (x,y,z)
- **Lecture**: hardware_service subscriber

## Cameras

### Camera Front (chassis)
- **Device**: /dev/video0 (CAMERA_FRONT_INDEX=0)
- **Lib**: OpenCV (cv2.VideoCapture)
- **Usage**: AnalyzeScene, RecognizeFace, RecognizeObject, RecognizeQRCode
- **Resolution**: 640x480

### Camera Claw (bras)
- **Device**: /dev/video2 (CAMERA_CLAW_INDEX=2)
- **Lib**: OpenCV
- **Usage**: vue proche de la pince

### Camera 3D Orbbec Astra Pro+
- **Model**: Astra Pro+ (serial ACRMB43003E)
- **Capabilities**: RGB + Depth (640x480@30Hz)
- **Driver**: astra_camera (ros2_astra_camera)
- **Service**: orbbec-camera.service (active)
- **Usage**: potentiel SLAM 3D (RTAB-Map), depth fusion
- **Topics**: /camera/color, /camera/depth

## Batterie
- **Topic**: /voltage (std_msgs/Float32)
- **Lecture**: hardware_service subscriber
- **Plage**: 9.6V - 12.6V (3S LiPo)
- **Endpoint**: GET /battery

## YOLO (Vision)
- **Node**: yolo_detector.py
- **Model**: yolov5s (yolov5_env: Python 3.10, torch 2.5, cv2 4.11)
- **FPS**: 5-10 Hz sur Jetson Orin
- **Topics**: /detections (JSON), /camera/detection_image (CompressedImage)
- **Service**: yolo-detector.service (manuel, non auto-start)
- **Endpoints**: GET /yolo/frame, GET /yolo/status