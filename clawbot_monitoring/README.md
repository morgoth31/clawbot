# clawbot_monitoring

**Web Dashboard for Real-Time Robot Status & Control**

## Purpose
Provides a live web UI (port 5000) to monitor and control the clawbot. Shows sensor data (battery, IMU, camera feeds), SLAM map visualization, servo angles, and emergency controls.

## Architecture

### Files
- **`app.py`**: Flask backend (routes, data aggregation, WebSocket)
  - Polls hardware_service (port 8000) for telemetry
  - Forwards user commands (buttons, sliders) → hardware_service
  - Streams camera feeds (front/claw cameras)
- **`ui/`**: React SPA (single-page app)
  - Dashboard card layout (battery, SLAM map, servo status, camera feed)
  - Real-time updates via WebSocket
  - Sliders for servo angles, velocity commands
- **`static/`**: Built React assets (index.html, bundle.js)
- **`Dockerfile`**: Flask + Node.js build, runs on port 5000

### Key Features
1. **Live Telemetry**
   - Battery voltage
   - IMU data (accel, gyro, orientation)
   - Servo angles (all 6 joints)
   - Wheel odometry (x, y, theta)

2. **SLAM Map Viewer**
   - Displays live /map topic
   - Shows robot pose (red marker)
   - Saved maps list + load/delete UI

3. **Camera Feeds**
   - Front camera (wide view)
   - Claw camera (gripper-mounted)
   - Real-time MJPEG or base64 polling

4. **Control Panel**
   - Velocity sliders (linear_x, linear_y, angular_z)
   - Servo angle sliders (joint 1-5, gripper)
   - Emergency stop button
   - Beep/lamp test controls

## Data Flow

```
app.py (Flask + WebSocket)
    ↓ [HTTP GET every 100ms]
hardware_service.py (port 8000)
    ↓ [ROS2 subscriptions + serial reads]
Robot sensors (odometry, IMU, servos)
    ↓ [WebSocket push to React]
Browser UI (real-time dashboard)
```

## Integration

- **Backend**: Expects hardware_service on `localhost:8000`
- **ROS2 Topics** (read):
  - `/battery_voltage`, `/imu/data`, `/servo_status`, `/cmd_vel_raw`, `/map`
- **ROS2 Topics** (write):
  - `/cmd_vel`, `/servo_ctrl`, `/beep`, `/lamp_color`
- **Port**: 5000 (internal HTTP + WebSocket)

## Development

### Frontend Changes
Modify React components in `ui/` → run `npm run build` → copies to `static/` → Docker rebuild needed

### Backend Changes
Edit `app.py` → restart Flask container

## Docker Compose Integration
Part of `docker-compose.yml` in `ros2_llm_bridge/`:
```yaml
monitoring:
  build: ./clawbot_monitoring
  ports:
    - "5000:5000"
  environment:
    - HARDWARE_SERVICE_URL=http://bridge:8000
```

## Known Limitations
- **Latency**: WebSocket updates ~100-200ms (HTTP polling bottleneck)
- **Camera Frames**: Low FPS if images are large (may need compression)
- **Map Refresh**: SLAM map updates on demand (not continuous streaming)

## Status
✅ Operational. Basic dashboard working.  
🔧 TODO: Foxglove Bridge integration for richer visualization (planned).

**Maintainer**: clawbot developers
