# joy_teleop

**Nintendo Pro Controller Teleoperation Interface**

## Purpose
Maps Nintendo Pro Controller input to robot motion & arm commands. Enables real-time direct control via USB-C (fully functional) or Bluetooth (pending kernel support).

## Architecture

### Files
- **`clawbot_joy_teleop.py`**: Main ROS2 node
  - Subscribes `/joy` (sensor_msgs/Joy from hid-nintendo)
  - Publishes `/cmd_vel` (motion), `/servo_ctrl` (arm), `/beep`, `/lamp_color`
  - Deadman switch (ZR button) for safety
  
- **`joy_teleop_launch.py`**: ROS2 launch file (starts joy node + teleop node)
- **`identify_mapping.py`**: Helper to test/identify button mappings
- **`test_controller.py`**: Standalone test script (no ROS2 needed)

## Button Mapping

### Current (hid-nintendo USB-C only)
| Button | Function | Details |
|--------|----------|---------|
| **ZR** | Deadman (enable) | Must hold to send commands |
| **ZL** | Arm mode toggle | Switches between wheel/arm control |
| **L/R** | Unused (reserved) | – |
| **A** | Gripper close | Servo 6 → 180° |
| **B** | Gripper open | Servo 6 → 0° |
| **X** | Unused | – |
| **Y** | Unused | – |
| **±** | Reserved | – |
| **LStick** | Wheel motion | LX=strafe, LY=forward, RX=rotate |
| **RStick** | Arm (if enabled) | RY=pan, RX=tilt (future) |
| **DPad** | Servo selection | Up/Down = joint ±5°, L/R = next joint |

### Axis Mapping (hid-nintendo)
- **Axis 0 (LX)**: -1.0 (left) to +1.0 (right) — lateral/strafe
- **Axis 1 (LY)**: -1.0 (down/forward) to +1.0 (up/back)
- **Axis 2 (RX)**: -1.0 (left) to +1.0 (right) — rotate
- **Axis 3 (RY)**: -1.0 (down) to +1.0 (up) — vertical motion / pan
- **Axis 6 (DX)**, **Axis 7 (DY)**: D-Pad horizontal/vertical

## Hardware Setup

### USB-C Path (✅ Working)
```
hid-nintendo DKMS (v3.2) → /dev/input/js0 → ros2 joy node → /joy topic
```
- **Driver**: `/usr/src/nintendo-3.2/` (DKMS kernel module)
- **Device**: `/dev/input/js0` (joystick interface)
- **Status**: Fully functional; auto-detected on boot

### Bluetooth Path (❌ Pending)
```
joycond daemon → /dev/input/js[X] → ros2 joy node
```
- **Blocker**: Linux kernel 5.15.148-tegra missing HIDP socket support
- **Workaround**: Use USB-C only
- **joycond** installed @ `/usr/bin/joycond` (ready when kernel fixed)

## ROS2 Integration

### Startup
```bash
ROS_DOMAIN_ID=28 ros2 launch joy_teleop/joy_teleop_launch.py
```

### Topics
- **Subscribe**: `/joy` (sensor_msgs/Joy) ← hid-nintendo driver
- **Publish**:
  - `/cmd_vel` (geometry_msgs/Twist) → hardware_service
  - `/servo_ctrl` (clawbot_msgs/ServoCommand) → hardware_service
  - `/beep` (std_msgs/Bool) → buzzer
  - `/lamp_color` (std_msgs/Int32Array) → RGB LEDs

### Systemd Service
- **Name**: `clawbot-joy-teleop.service`
- **Enabled**: Yes (auto-starts on boot after hardware_service + driver_node)
- **Logs**: `journalctl -u clawbot-joy-teleop -f`

## Configuration

### Speed Limits (in `clawbot_joy_teleop.py`)
- **Max linear**: ±0.06 m/s (hardware limit)
- **Max angular**: ±0.25 rad/s (hardware limit)
- **Deadman**: Must hold ZR throughout

### Servo Limits
- **Range**: 0–180° per servo
- **Speed**: Configurable (currently hardware-limited to ~30°/s)

## Testing

### Identify Button Mapping
```bash
python3 /home/jetson/clawbot/joy_teleop/identify_mapping.py
# Press buttons; outputs event numbers
```

### Standalone Test (no ROS2)
```bash
python3 /home/jetson/clawbot/joy_teleop/test_controller.py
# Reads /dev/input/js0 directly
```

## Known Issues
- **Axis Inversion**: DPad Y-axis may be inverted (DY swapped)
- **Slow Response**: Poll rate ~100Hz; consider higher if lag detected
- **Bluetooth**: Blocked by kernel. Use USB-C.

## Future Work
- [ ] Arm IK solver (instead of manual servo selection)
- [ ] Profile system (different button mappings for different tasks)
- [ ] Haptic feedback (rumble on collision warnings)

**Status**: ✅ Production (USB-C). Tested on Pro Controller v2.

**Maintainer**: clawbot developers
