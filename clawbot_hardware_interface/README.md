# clawbot_hardware_interface

**ROS2 Control Hardware Plugin for Arm & Motion**

## Purpose
Implements ROS2 Control plugin (`ros2_control`) for the clawbot arm and differential drive. Bridges `ros2_control` framework with actual hardware (servos, wheels) via systemd hardware service on port 8001.

## Architecture

### Files
- **`src/`**: C++ hardware interface implementation (lifecycle + state interface)
- **`config/`**: Parameter configs for servo IDs, acceleration limits, PID gains
- **`launch/`**: ROS2 launch files to spawn hardware interface + controller manager
- **`include/`**: Header files for hardware interface class
- **`clawbot_hardware_interface.xml`**: Plugin descriptor for ros2_control

### Dependencies
- `ros2_control` (hardware_interface library)
- `pluginlib` (dynamic plugin loading)
- `rclcpp` (C++ ROS2 client)
- TCP/HTTP to hardware_service (port 8001) for servo commands

## Workflow

```
ROS2 Control Manager (controller_manager)
        ↓ [loads plugin via XML]
  clawbot_hardware_interface
        ↓ [on_init, on_configure, on_activate]
  HTTP POST to http://localhost:8001/command
        ↓
  hardware_service.py → Rosmaster_Lib → /dev/myserial
        ↓
  Servos (ID 1-6), Wheels (Mecanum)
```

1. Hardware interface registers **state interfaces** (joint positions/velocities, IMU)
2. Hardware interface registers **command interfaces** (joint targets, wheel speeds)
3. Controller Manager reads states → runs control loop → writes commands
4. Commands send HTTP requests to hardware_service; responses update state

## Key Components

### Servo Control (Arm)
- **Servo IDs**: 1-6 (shoulder, elbow, wrist 2-axis, gripper)
- **Range**: 0–180° per servo config
- **Command**: ControlServo(id, angle), read back via /servo_status topic

### Motion Control (Wheels)
- **Type**: Mecanum differential drive
- **Command**: SetVelocity(linear_x, linear_y, angular_z)
- **Odometry**: `/odom` from hardware_service (Rosmaster calibration)

## Known Issues
- **Serial Conflict**: This plugin depends on hardware_service.py holding `/dev/myserial` exclusively
- **Odom Bug**: When both driver_node and hardware_service run, serial packets collide → /odom reads 0,0
- **Workaround**: Use this interface only in "full ROS2 control" mode; for SLAM, run hardware_service alone

## Status
- ✅ Compiled (C++ hardware interface)
- ⚠️ Integration pending: MoveIt2 planning not yet integrated
- ⚠️ Testing: Servo speed limits + acceleration profiles need calibration

## Integration Points
- **Port 8001**: hardware_service.py listens here
- **ROS2 Domain**: 28 (must match all nodes)
- **Launch**: Expects `ros2_control_node` + `controller_manager` spawned together
- **Topics**: Subscribes `/cmd_vel` (geometry_msgs/Twist)

**Maintainer**: ohlimi@gmail.com
