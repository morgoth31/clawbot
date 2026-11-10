# services

**Systemd Service Definitions for Auto-Start**

## Purpose
Contains systemd unit files to auto-start clawbot services at boot. Enables unattended operation without manual terminal commands.

## Service Files

| Service | Enabled | Startup Order | Purpose |
|---------|---------|---------------|---------|
| **ros2-hardware-service.service** | ✅ Yes | 1st | Hardware API bridge (port 8000) |
| **ros2-driver-node.service** | ✅ Yes | 2nd | ROS2 wheel driver (Mcnamu_driver_X3) |
| **ros2-llm-bridge.service** | ✅ Yes | 3rd | Docker compose (monitoring + bridge) |
| **clawbot-joy-teleop.service** | ✅ Yes | 4th | Nintendo Pro Controller input |
| **orbbec-camera.service** | ❌ Manual | — | Astra Pro+ RGB-D camera |
| **yolo-detector.service** | ❌ Manual | — | YOLOv5 object detection |
| **rosbridge.service** | ✅ Yes | 5th | ROS Bridge (WebSocket, port 9090) |

### Enabled vs Manual
- **Enabled**: Auto-start on boot; part of `multi-user.target`
- **Manual**: Available but not auto-started; use `systemctl start <name>`

## Service Details

### 1. ros2-hardware-service.service
```
[Unit]
Description=Clawbot Hardware Service
After=network.target
Wants=ros2-driver-node.service

[Service]
ExecStart=python3 /home/jetson/clawbot/ros2_llm_bridge/hardware_service.py
Environment="ROS_DOMAIN_ID=28"
Restart=on-failure
User=jetson

[Install]
WantedBy=multi-user.target
```
- **Dependency**: Must run before driver_node (serial port exclusive)
- **Port**: 8000 (HTTP), 8001 (monitor)

### 2. ros2-driver-node.service
```
[Unit]
Description=Clawbot ROS2 Driver Node
After=ros2-hardware-service.service

[Service]
ExecStart=ros2 run yahboomcar_bringup Mcnamu_driver_X3.py
Environment="ROS_DOMAIN_ID=28"
Restart=on-failure
User=jetson

[Install]
WantedBy=multi-user.target
```
- **Depends On**: ros2-hardware-service (serial exclusive)
- **Conflict**: Cannot run with hardware_service (both claim `/dev/myserial`)

### 3. ros2-llm-bridge.service
```
[Unit]
Description=Clawbot LLM Bridge + Monitoring
After=ros2-hardware-service.service

[Service]
WorkingDirectory=/home/jetson/clawbot/ros2_llm_bridge
ExecStart=docker compose up
Restart=always
User=jetson

[Install]
WantedBy=multi-user.target
```
- **Includes**: monitoring dashboard (port 5000) + bridge API (duplicates hardware_service)

### 4. clawbot-joy-teleop.service
```
[Unit]
Description=Clawbot Joy Teleop Controller
After=ros2-driver-node.service

[Service]
ExecStart=ros2 run joy_teleop clawbot_joy_teleop.py
Environment="ROS_DOMAIN_ID=28"
Restart=on-failure
User=jetson

[Install]
WantedBy=multi-user.target
```
- **Dependencies**: hid-nintendo driver + Pro Controller plugged in

### 5. orbbec-camera.service (Manual)
```
[Unit]
Description=Orbbec Astra Pro+ Camera

[Service]
ExecStart=ros2 launch orbbec_camera astra_pro_plus.launch.xml
Environment="ROS_DOMAIN_ID=28"
Restart=on-failure
User=jetson

[Install]
WantedBy=multi-user.target
```
- **Status**: Not auto-enabled (manual `systemctl start orbbec-camera`)
- **Topics**: `/camera/color/image_raw`, `/camera/depth/image_rect_raw`, etc.

### 6. yolo-detector.service (Manual)
```
[Unit]
Description=YOLO Object Detection Node

[Service]
ExecStart=python3 /home/jetson/clawbot/yolo_node/yolo_detector.py
Environment="ROS_DOMAIN_ID=28"
Restart=on-failure
User=jetson

[Install]
WantedBy=multi-user.target
```
- **Status**: Manual start (GPU-heavy; disable if not needed)

### 7. rosbridge.service
```
[Unit]
Description=ROS Bridge WebSocket Server
After=ros2-driver-node.service

[Service]
ExecStart=ros2 launch rosbridge_server rosbridge_websocket_launch.xml
Environment="ROS_DOMAIN_ID=28"
Restart=on-failure
User=jetson

[Install]
WantedBy=multi-user.target
```
- **Port**: 9090 (WebSocket)
- **Use**: Foxglove, web dashboards, remote access

## Management

### Enable Service at Boot
```bash
sudo systemctl enable ros2-hardware-service.service
```

### Disable (prevent auto-start)
```bash
sudo systemctl disable ros2-driver-node.service
```

### Check Status
```bash
systemctl status ros2-hardware-service.service
```

### View Logs (live)
```bash
journalctl -u ros2-hardware-service.service -f
```

### Start/Stop Manually
```bash
sudo systemctl start ros2-hardware-service.service
sudo systemctl stop ros2-hardware-service.service
sudo systemctl restart ros2-hardware-service.service
```

## Startup Order (Dependency Tree)

```
multi-user.target
    ├→ [1] ros2-hardware-service.service
    │       ├→ [2] ros2-driver-node.service ⚠️ SERIAL CONFLICT
    │       ├→ [3] ros2-llm-bridge.service (docker compose)
    │       └→ [5] rosbridge.service
    └→ [4] clawbot-joy-teleop.service
        (manual) orbbec-camera.service
        (manual) yolo-detector.service
```

**Critical**: `ros2-driver-node` conflicts with `hardware_service` over `/dev/myserial`.  
Choose one operation mode:
- **API Mode**: Run hardware_service only (for LLM + monitoring)
- **ROS2 Native**: Run driver_node only (for traditional ROS2 stack)

## Deployment

### Install All Services
```bash
bash /home/jetson/clawbot/services/deploy_services.sh
```

This script:
1. Copies `.service` files to `/etc/systemd/system/`
2. Runs `systemctl daemon-reload`
3. Enables selected services
4. Starts them in order

### Manual Install
```bash
sudo cp ros2-hardware-service.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ros2-hardware-service.service
sudo systemctl start ros2-hardware-service.service
```

## Troubleshooting

### Service Fails to Start
```bash
journalctl -u ros2-hardware-service -n 50
# Check error messages; common issues:
# - Port already in use (change port in config)
# - Python venv not activated (use absolute /usr/bin/python3)
# - ROS_DOMAIN_ID mismatch (must be 28)
```

### Services Stuck in Failed State
```bash
sudo systemctl reset-failed ros2-hardware-service.service
```

### Serial Port Locked
```bash
# Check which process holds /dev/myserial
lsof /dev/myserial

# If stale lock, stop the service:
sudo systemctl stop ros2-hardware-service.service
# Wait 5s, restart
sudo systemctl start ros2-hardware-service.service
```

## Future Work
- [ ] Watchdog timer (auto-restart failed services)
- [ ] Health monitoring dashboard (service status + logs)
- [ ] Config file for enabling/disabling services (instead of hardcoded)

**Status**: ✅ Operational. 5/8 services auto-start on boot.

**Maintainer**: clawbot team
