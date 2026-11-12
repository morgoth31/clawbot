---
type: Infrastructure
title: "Services Systemd -- 6 Services Auto-Start"
description: Services systemd du Clawbot avec ordre de demarrage et dependances.
status: stable
tags: [systemd, services, infrastructure]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:30:00Z
sources:
  - id: services-dir
    resource: file:///home/jetson/clawbot/services/
    title: services/ directory
    author: human:jetson
    last_modified: 2026-03-06
---

# Services Systemd

## Ordre de Demarrage

| # | Service | Description | Port | Status |
|---|---------|-------------|------|--------|
| 1 | ros2-hardware-service.service | Hardware API (FastAPI) | 8001 | active |
| 2 | ros2-driver-node.service | Driver roues (Mcnamu_driver_X3) | - | active |
| 3 | ros2-llm-bridge.service | Docker compose (bridge + monitoring) | 8000, 5000 | active |
| 4 | clawbot-joy-teleop.service | Manette Nintendo Pro | - | active |
| 5 | rosbridge.service | WebSocket Foxglove | 9090 | active |
| 6 | orbbec-camera.service | Camera Astra Pro+ | - | active |

## Services Manuels (non auto-start)
- yolo-detector.service -- Detection YOLOv5

## Details par Service

### 1. ros2-hardware-service.service
- **ExecStart**: python3 hardware_service.py
- **After**: network.target
- **Env**: ROS_DOMAIN_ID=28, WORKSPACE_PATH=/home/jetson/.openclaw/workspace
- **Dependances**: aucune (premier a demarrer)

### 2. ros2-driver-node.service
- **ExecStart**: ros2 run yahboomcar_bringup Mcnamu_driver_X3
- **After**: network.target, ros2-hardware-service.service
- **Requires**: ros2-hardware-service.service
- **Note**: Conflit serial avec hardware_service (les deux utilisent /dev/myserial)

### 3. ros2-llm-bridge.service
- **ExecStart**: docker compose up
- **ExecStartPre**: docker compose down
- **Requires**: docker.service, ros2-hardware-service.service
- **After**: docker.service, network-online.target, ros2-hardware-service.service

### 4. clawbot-joy-teleop.service
- Manette Nintendo Pro Controller
- USB-C: fonctionnel
- Bluetooth: non (kernel 5.15.148-tegra)

### 5. rosbridge.service
- **ExecStart**: ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090
- **After**: network.target, ros2-driver-node.service
- **Requires**: ros2-driver-node.service
- **Usage**: Foxglove Studio -> ws://[IP]:9090

### 6. orbbec-camera.service
- Camera Orbbec Astra Pro+
- Depth 640x480@30Hz
- Serial: ACRMB43003E