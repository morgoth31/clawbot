---
type: API Reference
title: "Hardware Service -- Catalogue des Endpoints (30+)"
description: Liste complete des endpoints REST du hardware_service sur le port 8001.
status: stable
tags: [api, rest, hardware, endpoints]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:20:00Z
sources:
  - id: hw-service-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/hardware_service.py
    title: hardware_service.py
    author: human:jetson
    last_modified: 2026-03-01
---

# Hardware Service -- Endpoints (port 8001)

## Motion

### POST /motion
Body: `{"linear_x": float, "linear_y": float, "angular_z": float}`
Publie sur /cmd_vel. Applique safety clamping. Retourne les valeurs clampes.
HTTP 409 si obstacle detecte (LiDAR).

### POST /motion/stop
Arret immediat. Publie Twist() sur /cmd_vel.

## Servos & Arm

### POST /servo
Body: `{"servo_id": int, "angle": float}`
Publie sur /servo_ctrl. Controle un servo individuel (1-6).

### POST /arm
Body: `{"joints": [float, float, float, float, float]}`
5 angles pour servos 1-5 (bras 5-DOF).

### POST /claw
Body: `{"state": "open" | "close"}`
Controle la pince (servo 6). open=0, close=180.

### POST /arm/pose/{pose_id}
Pose predefinie: 1=anti-collision, 2=dance, 3=line-tracking.

## Peripherals

### POST /beep
Query: `delay_ms` (1-5000)
Buzzer pendant X ms.

### POST /lamps
Body: `{"r": int, "g": int, "b": int}`
Couleur LEDs RGB (0-255 chaque).

## Telemetry

### GET /battery
Retourne voltage + pourcentage charge (3S LiPo).

### GET /telemetry
Retourne: battery, IMU (accel + gyro), velocity (vx, vy, angular), servo_angles.

### GET /system/status
Retourne: etat services systemd, docker, nodes ROS2, topics, CPU/memoire.

## Vision

### GET /capture
Query: `camera=front|claw`, `save=true|false`
Capture une frame JPEG. Retourne base64 + saved_path si save=true.

### GET /yolo/frame
Retourne image YOLO annotee (base64) + detections JSON.

### GET /yolo/status
Retourne l'etat du service yolo-detector.

## SLAM & Maps

### POST /slam/start
Lance Cartographer SLAM via subprocess (tmux session).

### POST /slam/stop
Arrete le SLAM.

### GET /slam/status
Retourne: running, nodes actifs, duree.

### GET /map/live
Retourne la carte SLAM actuelle (OccupancyGrid -> PNG base64).

### GET /maps
Liste les cartes sauvegardees dans /home/jetson/clawbot/maps/.

### POST /maps/save
Body: `{"name": str}`
Sauvegarde la carte actuelle (subprocess map_saver_cli).

### GET /maps/{name}/image
Retourne l'image PNG d'une carte sauvegardee.

### DELETE /maps/{name}
Supprime une carte sauvegardee.

## Health

### GET /health
Retourne `{"status": "healthy"}` si le node ROS2 est actif.