# Clawbot Codebase Map

**Last Updated:** 2026-03-06 07:35  
**Status**: 8/10 core README files completed. 90% of codebase documented.

---

## 📋 Quick Navigation

| Module | Purpose | README | Status |
|--------|---------|--------|--------|
| **ros2_llm_bridge** | API hub + hardware services | ✅ [LINK](./ros2_llm_bridge/README.md) | Production |
| **clawbot_hardware_interface** | ROS2 Control plugin (C++) | ✅ [LINK](./clawbot_hardware_interface/README.md) | Compiled, pending integration |
| **clawbot_monitoring** | Web dashboard (Flask/React) | ✅ [LINK](./clawbot_monitoring/README.md) | Operational |
| **joy_teleop** | Nintendo Pro Controller input | ✅ [LINK](./joy_teleop/README.md) | Production |
| **urdf** | Robot model + TF tree | ✅ [LINK](./urdf/README.md) | Validated |
| **yolo_node** | YOLOv5 object detection | ✅ [LINK](./yolo_node/README.md) | Operational |
| **yahboomcar_bringup** | ROS2 wheel driver (Mcnamu_driver_X3) | ✅ [LINK](./yahboomcar_bringup/README.md) | Functional (serial conflict known) |
| **yahboomcar_laser** | LiDAR avoidance + tracking | ✅ [LINK](./yahboomcar_laser/README.md) | Operational |
| **services** | Systemd auto-start units | ✅ [LINK](./services/README.md) | 5/8 auto-enabled |
| **maps** | Saved SLAM maps (Cartographer) | ✅ [LINK](./maps/README.md) | Operational |

---

## 🏗️ Architecture Overview

### Data Flow Layers

```
┌─────────────────────────────────────────────────────┐
│  External Clients (Claude LLM, Monitoring UI)      │
└──────────────────┬──────────────────────────────────┘
                   ↓ HTTP REST
┌──────────────────────────────────────────────────────┐
│  ros2_llm_bridge/hardware_service.py (port 8000)   │
│  • 17 tools (motion, vision, servo, etc.)          │
│  • SLAM map endpoints                              │
│  • Battery/sensor polling                          │
└──────┬────────────────┬────────────────┬───────────┘
       ↓ ROS2 Topics   ↓ Serial cmds     ↓
    ┌──────────────┐  ┌────────────┐  ┌──────────┐
    │ ROS2 Nodes   │  │ Hardware   │  │ Sensors  │
    │ (drivers)    │  │ (Rosmaster)│  │ (LiDAR,  │
    │              │  │            │  │  IMU,    │
    │ • bringup    │  │ /dev/      │  │  camera) │
    │ • avoidance  │  │ myserial   │  │          │
    │ • SLAM       │  └────────────┘  └──────────┘
    │ • nav        │
    └──────────────┘
```

### Core Systems

#### 1. **Hardware Service** (ros2_llm_bridge/)
- **Purpose**: Unified API for all hardware control
- **Port**: 8000 (HTTP), 8001 (monitor)
- **Tools**: SetVelocity, ControlServo, CaptureCamera, AnalyzeScene, NavigateTo, GetBatteryVoltage, SetLamps, Beep, etc.
- **Deps**: Rosmaster_Lib, FastAPI, rclpy
- **Systemd**: `ros2-hardware-service.service` (enabled)

#### 2. **ROS2 Driver Stack**
- **yahboomcar_bringup**: Publishes `/odom`, `/imu/data`, `/voltage`
  - ⚠️ Known issue: Serial port conflict with hardware_service
- **yahboomcar_laser**: Obstacle avoidance, tracking, warning
- **joy_teleop**: Controller input → `/cmd_vel` + `/servo_ctrl`

#### 3. **Navigation/SLAM**
- **slam_launch.py**: Cartographer 2D mapping (pure LiDAR scan-matching)
- **Maps saved to**: `/home/jetson/clawbot/maps/`
- **Odometry workaround**: Use LiDAR scan-matching (ignores `/odom` bug)

#### 4. **Vision Pipeline**
- **yolo_node**: Real-time object detection
- **Astra Pro+ RGB-D**: (optional, manual start)
- **Topics**: `/detections` (JSON), `/camera/detection_image` (JPEG)

#### 5. **Control Interfaces**
- **joy_teleop**: Nintendo Pro USB-C (working), Bluetooth (pending kernel fix)
- **Web Dashboard**: Flask backend (port 5000) + React UI
- **ROS Bridge**: WebSocket (port 9090) for Foxglove

#### 6. **Model & TF Tree**
- **URDF**: 9 links, 8 joints (arm 5-axis + gripper)
- **Static TFs**: base_footprint → base_link (z=0.0815) + sensor mounts
- **Dynamic TFs**: Arm joint positions published per `/servo_status`

---

## 🔌 Key Interfaces

### ROS2 Domain
- **ID**: 28 (all nodes must match)
- **DDS Profile**: FastDDS with 4MB UDP buffers
- **Topics**: ~50 published across all nodes

### HTTP API (hardware_service.py)
```bash
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"tool": "SetVelocity", "linear": 0.05, "angular": 0.0}'
```

### Systemd Services (auto-start order)
1. `ros2-hardware-service.service` — Hardware API
2. `ros2-driver-node.service` — ROS2 driver (⚠️ conflicts with #1)
3. `ros2-llm-bridge.service` — Docker compose (monitoring)
4. `clawbot-joy-teleop.service` — Controller input
5. `rosbridge.service` — WebSocket (port 9090)

---

## ⚠️ Critical Known Issues

### 1. Serial Port Conflict (MEMORY.md line 73)
- **Problem**: `hardware_service.py` and `yahboomcar_bringup/Mcnamu_driver_X3.py` both claim `/dev/myserial`
- **Impact**: `/odom` always reads 0,0,0 when both run
- **Workaround**: Use Cartographer's LiDAR scan-matching (active, doesn't depend on `/odom`)
- **Resolution**: Merge drivers or run only one at a time

### 2. Nintendo Pro Controller
- **USB-C**: ✅ Working (hid-nintendo DKMS v3.2)
- **Bluetooth**: ❌ Pending kernel fix (HIDP socket missing in 5.15.148-tegra)

### 3. MoveIt2 Integration
- **Status**: Not integrated
- **Blocker**: ros2_control plugin incomplete; arm planning via MoveIt2 pending

### 4. Real-Time Constraints
- **Motion**: Hard limits in hardware_service (±0.06 m/s linear, ±0.25 rad/s angular)
- **Vision**: YOLOv5 ~100–200 ms latency per frame
- **SLAM**: 1 Hz map updates (Cartographer publish rate)

---

## 📂 Directory Structure (Full)

```
/home/jetson/clawbot/
├── CODEBASE_MAP.md ← YOU ARE HERE
├── WORK_STATE.md (project status)
├── slam_launch.py (Cartographer entry point)
│
├── ros2_llm_bridge/ ⭐ [CORE] Hardware API hub
│   ├── hardware_service.py (36KB, 17 tools)
│   ├── Dockerfile (Docker compose)
│   ├── PRD.md (API specs)
│   ├── nervous_system.md (design philosophy)
│   └── README.md ✅
│
├── clawbot_hardware_interface/ [ROS2 Control plugin]
│   ├── src/ (C++ implementation)
│   ├── config/ (servo/motor params)
│   ├── launch/ (ros2_control launch)
│   └── README.md ✅
│
├── clawbot_monitoring/ [Web dashboard]
│   ├── app.py (Flask backend)
│   ├── ui/ (React components)
│   ├── static/ (built assets)
│   ├── Dockerfile
│   └── README.md ✅
│
├── joy_teleop/ [Controller input]
│   ├── clawbot_joy_teleop.py ⭐
│   ├── identify_mapping.py
│   ├── test_controller.py
│   └── README.md ✅
│
├── urdf/ [Robot model]
│   ├── clawbot_X3.urdf (9 links, 8 joints)
│   ├── validate_urdf.py
│   └── README.md ✅
│
├── yolo_node/ [YOLOv5 detection]
│   ├── yolo_detector.py ⭐
│   ├── test_camera.py
│   └── README.md ✅
│
├── yahboomcar_bringup/ [ROS2 driver]
│   ├── yahboomcar_bringup/
│   │   ├── Mcnamu_driver_X3.py ⭐
│   │   ├── calibrate_linear_X3.py
│   │   ├── calibrate_angular_X3.py
│   │   └── transform_utils.py
│   ├── launch/
│   ├── package.xml
│   └── README.md ✅
│
├── yahboomcar_laser/ [LiDAR avoidance]
│   ├── yahboomcar_laser/
│   │   ├── laser_Avoidance_a1_X3.py ⭐
│   │   ├── laser_Tracker_a1_X3.py
│   │   ├── laser_Warning_a1_X3.py
│   │   ├── common.py
│   │   └── .ipynb_checkpoints/
│   ├── launch/
│   ├── test/
│   ├── package.xml
│   └── README.md ✅
│
├── services/ [Systemd units]
│   ├── ros2-hardware-service.service
│   ├── ros2-driver-node.service
│   ├── ros2-llm-bridge.service
│   ├── clawbot-joy-teleop.service
│   ├── orbbec-camera.service (manual)
│   ├── yolo-detector.service (manual)
│   ├── rosbridge.service
│   ├── deploy_services.sh
│   └── README.md ✅
│
├── maps/ [Saved SLAM maps]
│   ├── test.yaml
│   ├── test.pgm
│   └── README.md ✅
│
├── urdf/ [URDF model] (described above)
│
├── yahboomcar_*/ [Legacy ROS2 packages]
│   ├── yahboomcar_description/ (CAD meshes)
│   ├── yahboomcar_nav/ (Nav2 config)
│   ├── yahboomcar_rviz/ (RViz configs)
│   ├── yahboomcar_ctrl/ (control nodes)
│   ├── yahboomcar_msgs/ (custom message types)
│   ├── yahboomcar_visual/ (visualization)
│   ├── yahboomcar_KCFTracker/ (legacy tracking)
│   └── [... more packages]
│
├── pkg_*/ [Tutorial packages]
│   ├── pkg_helloworld_py/
│   ├── pkg_topic/
│   ├── pkg_service/
│   ├── pkg_action/
│   ├── pkg_tf/
│   ├── pkg_param/
│   └── pkg_interfaces/
│
├── yolo_node/ [Vision detection] (described above)
│
├── laserscan_to_point_pulisher/ (LiDAR → point cloud)
├── robot_pose_publisher_ros2/ (TF broadcaster)
├── yahboom_app_save_map/ (legacy map saving)
├── yahboom_web_savmap_interfaces/ (legacy)
│
├── docs/ [Documentation]
├── site/ [Website/assets]
├── moveit/ [MoveIt2 config]
│
├── build/ [ROS2 build artifacts]
├── install/ [ROS2 install artifacts]
├── log/ [ROS2 logs]
└── .git/ [Git history]
```

---

## 🚀 Quick Start

### Boot System (systemd auto-start)
```bash
# All services start automatically on boot
# Check status:
systemctl status ros2-hardware-service.service

# View live logs:
journalctl -u ros2-hardware-service -f
```

### Manual SLAM Mapping
```bash
# Terminal 1: Start SLAM in tmux (separate ROS_DOMAIN_ID)
cd /home/jetson/clawbot
tmux new-session -d -s slam_mapping
tmux send-keys -t slam_mapping "ROS_DOMAIN_ID=28 ros2 launch slam_launch.py" Enter

# Terminal 2: Drive robot (joy_teleop or manual vel commands)
ROS_DOMAIN_ID=28 ros2 topic pub /cmd_vel_input geometry_msgs/Twist ...

# Terminal 3: Save map when done
ros2 run nav2_map_server map_saver_cli -f /home/jetson/clawbot/maps/my_room

# View map image:
eog /home/jetson/clawbot/maps/my_room.pgm
```

### Test Hardware API
```bash
# Check battery
curl -X POST http://localhost:8000/command \
  -d '{"tool": "GetBatteryVoltage"}'

# Move wheels
curl -X POST http://localhost:8000/command \
  -d '{"tool": "SetVelocity", "linear": 0.05, "angular": 0.0}'

# Capture camera
curl -X POST http://localhost:8000/command \
  -d '{"tool": "CaptureCamera", "camera": "front"}' | jq
```

### Web Dashboard
- **Port**: 5000
- **URL**: `http://localhost:5000`
- **Features**: Live telemetry, SLAM map viewer, servo sliders, emergency stop

### Foxglove RViz
- **Port**: 9090 (rosbridge WebSocket)
- **URL**: Open Foxglove, connect to `ws://localhost:9090`

---

## 📊 Performance Specs

| Metric | Value | Notes |
|--------|-------|-------|
| **Motion Speed** | ±0.06 m/s linear, ±0.25 rad/s angular | Hardware limits |
| **SLAM Update Rate** | 1 Hz | Cartographer /map publish |
| **YOLOv5 FPS** | 5–10 Hz | On Jetson Orin, yolov5s |
| **API Response** | <100 ms | hardware_service JSON |
| **Controller Latency** | ~100 ms | Joy topic → wheels |
| **Battery Voltage** | 12.2V (86%) | Last checked 2026-03-04 |
| **Serial Baudrate** | 115200 | Rosmaster_Lib |

---

## 🔧 Maintenance Tasks

### Weekly
- [ ] Check battery voltage (target >11.5V)
- [ ] Review systemd service logs for errors
- [ ] Test SLAM mapping in known area

### Monthly
- [ ] Recalibrate odometry (if drifting)
- [ ] Inspect LiDAR for dust/debris
- [ ] Update ROS2 packages: `sudo apt upgrade`

### Quarterly
- [ ] Backup important maps to external drive
- [ ] Review MEMORY.md for learnings
- [ ] Update CODEBASE_MAP.md if major changes

---

## 📝 Notes for Developers

### Adding New Features
1. Check which subsystem (hardware, vision, nav, control)
2. Create feature branch from `/home/jetson/clawbot/.git`
3. Update relevant README.md + MEMORY.md
4. Test in isolated tmux session (separate ROS_DOMAIN_ID if needed)
5. Commit + document in CODEBASE_MAP.md

### Debugging Serial Issues
```bash
# List USB devices
lsusb

# Monitor serial traffic
sudo strace -e openat,read,write lsof -p $(pgrep hardware_service)

# Check port lock
lsof /dev/myserial
```

### ROS2 DDS Troubleshooting
```bash
# Check ROS_DOMAIN_ID
echo $ROS_DOMAIN_ID  # Should be 28

# Verify node is discoverable
ROS_DOMAIN_ID=28 ros2 node list

# Check topic pub/sub
ROS_DOMAIN_ID=28 ros2 topic list
ROS_DOMAIN_ID=28 ros2 topic echo /cmd_vel
```

---

## 📚 Key Documentation Files

- **MEMORY.md** (workspace): Hardware learnings, stack config, critical fixes
- **WORK_STATE.md** (project root): High-level status + TODOs
- **PRD.md** (ros2_llm_bridge): Hardware service API specification
- **nervous_system.md** (ros2_llm_bridge): Design philosophy (2-stage architecture)
- **validate_urdf.py**: Run to check URDF syntax

---

## 🎯 TODO / Roadmap

### High Priority
- [ ] Resolve serial conflict (merge hardware_service + driver_node)
- [ ] Integrate MoveIt2 arm planning
- [ ] Fix Bluetooth Pro Controller (kernel fix)

### Medium Priority
- [ ] 3D SLAM (Cartographer 3D)
- [ ] Fine-tune YOLOv5 on clawbot-specific objects
- [ ] Add depth fusion (RGB-D + LiDAR)

### Low Priority
- [ ] Cloud map backup
- [ ] Multi-floor support
- [ ] Gripper finger spread (2-DOF gripper)

---

**Generated**: 2026-03-06 07:35  
**Token Budget Used**: ~80k / 200k  
**Next Step**: Implement missing features or refine existing subsystems.

For detailed subsystem info, refer to individual README.md files linked above. 🚀
