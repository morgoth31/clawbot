# ros2_llm_bridge

**The Robot's API Hub & Hardware Nervous System**

## Purpose
`ros2_llm_bridge` is the central command & control API for the clawbot. It exposes **17 hardware tools** via a unified REST API (port 8000) and manages bidirectional communication between:
- ROS2 hardware (servos, wheels, LiDAR, cameras)
- External clients (Claude, teleop, monitoring dashboard)
- ROS2 nodes (hardware_service, driver_node, sensors)

## Architecture

### Core Files
- **`hardware_service.py`** (36KB): Main FastAPI server + hardware tool implementations
  - 17 endpoints: SetVelocity, NavigateTo, ControlServo, CaptureCamera, AnalyzeScene, etc.
  - SLAM map management (save/load/image)
  - Battery monitoring, lamp/beep control
- **`entrypoint.sh`**: Docker startup script
- **`docker-compose.yml`** (inferred): Runs bridge + monitoring UI + LLM monitoring port 5000
- **`nervous_system.md`**: Design philosophy (2 autonomic + 3 processing stages)

### Key Dependencies
- FastAPI, uvicorn (REST API)
- rclpy (ROS2 Python client)
- Rosmaster_Lib (serial hardware abstraction)
- NumPy, OpenCV (vision processing)

### Service Integration
- **Systemd service**: `ros2-hardware-service.service`
- **Port**: 8000 (API), 5000 (monitoring)
- **Startup**: Docker compose (must run alongside hardware_service on port 8001)
- **Domain**: ROS_DOMAIN_ID = 28

## Workflow

1. **Client sends HTTP command** → `POST http://localhost:8000/command`
2. **hardware_service.py parses JSON** → maps tool + args
3. **Execute**: ROS2 pubs/subs + Rosmaster serial commands
4. **Return**: JSON response (status, data, error)

### Example Tools
- `SetVelocity` (linear m/s, angular rad/s) → wheels via `/cmd_vel`
- `ControlServo` (ID 1-6, angle) → servos via `/servo_ctrl`
- `CaptureCamera` (front/claw) → save to disk, return path
- `NavigateTo` (x, y) → SLAM map navigation
- `AnalyzeScene` → Vision analysis

## Known Issues
- **Serial Conflict**: hardware_service + driver_node both use `/dev/myserial` → must run only one at a time (see MEMORY.md)
- **SLAM Map Saves**: Must be run inside tmux `slam_mapping` session (separate ROS_DOMAIN_ID) to avoid DDS conflicts

## Dev Notes
- `docker-compose.yml` (not shown) handles container orchestration
- FastDDS profile @ `fastdds_profile.xml`: UDP buffers, DDS domain 28
- PRD.md contains detailed API specs and tool definitions
- Tests: pytest framework (requires setup.py)

## Quick Start
```bash
# Terminal 1: Hardware service (required)
cd /home/jetson/clawbot/ros2_llm_bridge
docker compose up -d

# Terminal 2: Test API
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"tool": "GetBatteryVoltage"}'
```

**Status**: Production. ~95% feature complete (MoveIt2 arm planning pending).
