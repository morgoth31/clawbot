# yahboomcar_bringup

**ROS2 Hardware Driver for Mecanum Wheels & IMU**

## Purpose
Core ROS2 driver node (`Mcnamu_driver_X3.py`) that bridges the Yahboom Rosmaster hardware library to ROS2. Manages:
- Mecanum wheel control via `/cmd_vel` (Twist)
- Servo command routing via `/servo_ctrl`
- IMU/sensor publishing (`/imu/data`, `/magnetic_field`)
- RGB lights and buzzer control
- Odometry estimation (problematic — see MEMORY.md)

## Files

### Main Drivers
- **`Mcnamu_driver_X3.py`** ⭐ (ACTIVE)
  - ROS2 node for X3 Mecanum platform
  - Subscribes: `/cmd_vel` (wheel motion), `/servo_ctrl` (arm commands), `/RGBLight`, `/Buzzer`
  - Publishes: `/odom`, `/imu/data`, `/magnetic_field`, `/voltage`
  - Serial communication via `Rosmaster_Lib` → `/dev/myserial`

- **`Mcnamu_driver_x1.py`** (legacy, similar)
- **`Ackman_driver_R2.py`** (Ackermann drive variant)
- **`patrol_a1_X3.py`, `patrol_4ROS.py`**: Autonomous patrol scripts (not drivers)
- **`calibrate_angular_X3.py`, `calibrate_linear_X3.py`**: Odometry calibration utilities

### Utilities
- **`transform_utils.py`**: TF helpers (frame transformations)

## Key Parameters

| Param | Type | Default | Purpose |
|-------|------|---------|---------|
| `car_type` | str | `X3` | Vehicle model |
| `imu_link` | str | `imu_link` | IMU frame name |
| `xlinear_limit` | float | 1.0 | Max linear X velocity (m/s) |
| `ylinear_limit` | float | 1.0 | Max linear Y velocity (m/s) |
| `angular_limit` | float | 5.0 | Max angular velocity (rad/s) |

## Architecture

```
ROS2 Nodes (Domain 28)
    ↓ [/cmd_vel Twist]
Mcnamu_driver_X3.py (yahboomcar_bringup)
    ↓ [serial frames]
Rosmaster_Lib (pure Python)
    ↓ [/dev/myserial]
Hardware (USB dongle → Mecanum controller)
    ↓
Wheels + Sensors
```

## Topics

### Subscriptions
| Topic | Type | Purpose |
|-------|------|---------|
| `/cmd_vel` | geometry_msgs/Twist | Wheel velocity commands |
| `/servo_ctrl` | std_msgs/Int32MultiArray | Servo angle commands [ID, angle, ...] |
| `/RGBLight` | std_msgs/Int32 | LED color (RGB packed int) |
| `/Buzzer` | std_msgs/Bool | Beep on/off |

### Publications
| Topic | Type | Purpose |
|-------|-------|---------|
| `/odom` | nav_msgs/Odometry | Wheel-based odometry (⚠️ broken) |
| `/imu/data` | sensor_msgs/Imu | IMU accelerometer + gyro |
| `/magnetic_field` | sensor_msgs/MagneticField | Compass |
| `/voltage` | std_msgs/Float32 | Battery voltage |

## Critical Issues

### ⚠️ Odometry Bug (MEMORY.md line 73)
When **both** `Mcnamu_driver_X3.py` and `hardware_service.py` run simultaneously:
- Both try to access `/dev/myserial` exclusively
- Serial packets collide → `get_motion_data()` returns 0
- `/odom` published as (0, 0, 0) for all time
- **Workaround**: Run only ONE of:
  - `hardware_service.py` alone (for SLAM + API calls)
  - `Mcnamu_driver_X3.py` alone (for pure ROS2 control)
  - Use Cartographer's LiDAR scan-matching instead (ignores odom)

### ⚠️ Serial Port Locking
- `/dev/myserial` → symlink to `/dev/ttyUSB1`
- Only one process can hold the serial handle at a time
- See `systemd` service configs for startup order

## Systemd Service

**Name**: `ros2-driver-node.service`  
**Enabled**: Yes (auto-starts after hardware-service in multi-user.target)

```bash
# View logs
journalctl -u ros2-driver-node -f

# Manual start
sudo systemctl start ros2-driver-node
```

## Usage

### Standalone ROS2
```bash
ROS_DOMAIN_ID=28 ros2 run yahboomcar_bringup Mcnamu_driver_X3.py
```

### With Launch File
```bash
ROS_DOMAIN_ID=28 ros2 launch yahboomcar_bringup bringup.launch.py
```

### Send Wheel Commands
```bash
ROS_DOMAIN_ID=28 ros2 topic pub /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.05, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

## Calibration

If odometry drifts significantly:

1. **Linear calibration**:
   ```bash
   python3 calibrate_linear_X3.py
   # Follow robot with tape measure, record distance traveled vs reported
   # Adjust scaling factor in Mcnamu_driver_X3.py line ~150
   ```

2. **Angular calibration**:
   ```bash
   python3 calibrate_angular_X3.py
   # Record rotation angle, adjust gyro bias/scale
   ```

## Dependencies

- **Rosmaster_Lib**: Python library for Yahboom hardware (vendored, not public)
  - Abstracts serial protocol for wheels, servos, sensors
- **rclpy**: ROS2 Python client
- **sensor_msgs**, **geometry_msgs**: ROS2 message types

## ROS2 Control Integration

This driver is **independent** of `clawbot_hardware_interface` (C++ ros2_control plugin).
Choose one:
- **Option A**: Use this driver (`yahboomcar_bringup`) + manual topic publishing
- **Option B**: Use C++ hardware interface (`clawbot_hardware_interface`) + controller manager

Current setup: **Option A** (simpler, faster iteration).

## Future Work

- [ ] Fix serial conflict by merging with hardware_service.py
- [ ] Implement wheel encoder-based odometry (more accurate than IMU)
- [ ] ROS2 Control compatibility layer (adopt Option B for MoveIt2)
- [ ] Kalman filter for odom fusion (IMU + wheel encoder + LiDAR)

**Status**: ✅ Functional. Serial conflict known; SLAM uses LiDAR only.

**Maintainer**: Yahboom (original), clawbot team (adaptations)
