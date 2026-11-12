---
type: Hardware Service
title: "Hardware Service -- API REST (port 8001)"
description: Le systeme nerveux du robot. Serveur FastAPI sur le host avec controle direct du hardware via ROS2 topics et OpenCV.
status: stable
tags: [hardware, fastapi, ros2, opencv, serial]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:20:00Z
sources:
  - id: hw-service-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/hardware_service.py
    title: hardware_service.py (979 lignes)
    author: human:jetson
    last_modified: 2026-03-01
  - id: hw-service-svc
    resource: file:///home/jetson/clawbot/services/ros2-hardware-service.service
    title: ros2-hardware-service.service
    author: human:jetson
    last_modified: 2026-03-06
---

# Hardware Service

## Role

Le hardware_service est le "systeme nerveux" du robot. C'est un serveur FastAPI
qui tourne sur le host Jetson (pas Docker) avec acces direct aux devices.
Il est le SEUL processus qui publie sur les topics ROS2 de controle.

## Configuration

- **Port**: 8001
- **Chemin**: `/home/jetson/clawbot/ros2_llm_bridge/hardware_service.py`
- **Taille**: 979 lignes, 36KB
- **Systemd**: `ros2-hardware-service.service` (enabled, auto-start)
- **ROS_DOMAIN_ID**: 28

## Topics ROS2

### Publishers
| Topic | Type | Usage |
|-------|------|-------|
| /cmd_vel | geometry_msgs/Twist | Commandes de vitesse |
| /servo_ctrl | std_msgs/Int32MultiArray | Angles des servos |
| /Buzzer | std_msgs/Bool | Buzzer on/off |
| /RGBLight | std_msgs/Int32 | Couleur LEDs |

### Subscribers
| Topic | Type | Usage |
|-------|------|-------|
| /voltage | std_msgs/Float32 | Tension batterie |
| /imu/data_raw | sensor_msgs/Imu | Accelerometre + gyroscope |
| /vel_raw | geometry_msgs/Twist | Vitesse mesuree (encodeurs) |
| /map | nav_msgs/OccupancyGrid | Carte SLAM |
| /camera/detection_image | sensor_msgs/CompressedImage | Image YOLO annotee |
| /detections | std_msgs/String | JSON detections YOLO |

## Safety Limits (hard-enforced)

| Limite | Valeur | Variable env |
|--------|--------|-------------|
| Linear max | 0.06 m/s | MAX_LINEAR_MS |
| Angular max | 0.25 rad/s | MAX_ANGULAR_RS |
| Watchdog | 1.5 s | MOTION_WATCHDOG_S |
| LiDAR safety | false (bypass) | LIDAR_SAFETY_REQUIRED |

Le watchdog arrete le robot si aucune commande de mouvement n'est recue
dans les 1.5 secondes.

## Variables d'Environnement

| Variable | Default | Description |
|----------|---------|-------------|
| ROS_DOMAIN_ID | 28 | Domaine ROS2 |
| CAMERA_FRONT_INDEX | 0 | /dev/video0 |
| CAMERA_CLAW_INDEX | 2 | /dev/video2 |
| HARDWARE_SERVICE_PORT | 8001 | Port HTTP |
| MAX_LINEAR_MS | 0.06 | Vitesse lineaire max |
| MAX_ANGULAR_RS | 0.25 | Vitesse angulaire max |
| MOTION_WATCHDOG_S | 1.5 | Timeout watchdog |
| LIDAR_SAFETY_REQUIRED | false | Safety LiDAR on/off |
| WORKSPACE_PATH | /home/jetson/.openclaw/workspace | Sauvegarde images |

## Architecture Interne

```
HardwareNode (rclpy.Node)
  -> Publishers: /cmd_vel, /servo_ctrl, /Buzzer, /RGBLight
  -> Subscribers: /voltage, /imu, /vel_raw, /map, /yolo
  -> Etat: battery, imu, velocity, servo_angles, map_data

FastAPI (uvicorn)
  -> Endpoints REST (30+)
  -> Appels directs au HardwareNode (publish)
  -> OpenCV pour cameras (cv2.VideoCapture)
  -> Subprocess pour SLAM/map management
```

## Pourquoi sur le host et pas Docker?

1. **Acces devices**: /dev/video0, /dev/video2 (cameras OpenCV)
2. **Pas de conflit serial**: communique via topics ROS2, pas /dev/myserial direct
3. **Performance**: pas de overhead Docker pour le traitement temps reel
4. **Subprocess**: lance ros2 launch pour SLAM, map_saver via subprocess