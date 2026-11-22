# yahboomcar_laser

**LiDAR-Based Obstacle Avoidance & Tracking**

## Purpose
Implements reactive obstacle avoidance and object tracking using a 2D LiDAR scanner. Provides three main capabilities:
1. **Avoidance**: Scan environment → avoid obstacles in motion
2. **Tracking**: Follow a detected object (e.g., person, ball)
3. **Warning**: Alert when obstacle too close

## Files

### Core Modules
- **`laser_Avoidance_a1_X3.py`** ⭐ (ACTIVE)
  - Mecanum X3 obstacle avoidance
  - Subscribes: `/scan` (LaserScan), `/cmd_vel_input` (desired motion)
  - Publishes: `/cmd_vel` (safe motion, avoidance-adjusted)

- **`laser_Tracker_a1_X3.py`**
  - Follow-the-target behavior
  - Finds nearest non-ground object in scan → tracks it

- **`laser_Warning_a1_X3.py`**
  - Safety monitor
  - Publishes `/emergency_stop` if obstacle within threshold

- **`laser_Avoidance_4ROS_R2.py`, `laser_Tracker_4ROS_R2.py`**
  - R2 (Ackermann) drive variants

- **`common.py`**
  - Shared utilities (scan parsing, angle conversions, geometry)

### Launch Files
- **`launch/laser_Avoidance_a1_X3.launch.py`**
  - ROS2 launch entry point for avoidance node

## Algorithm

### Obstacle Avoidance
```
Input: /scan (LaserScan from LiDAR)
       /cmd_vel_input (desired velocity from user)

1. Parse scan rays → extract minimum distance per angle sector
2. Check front sectors:
   if (front_distance < SAFE_DISTANCE):
       - Reduce forward velocity
       - Rotate away from obstacle
       - Publish adjusted /cmd_vel
   else:
       - Pass through original velocity
3. Output: /cmd_vel (safe, obstacle-aware)
```

### Tracking
```
Input: /scan

1. Filter rays (remove ground reflections)
2. Find nearest object in front (angular range ±45°)
3. Calculate heading error (desired vs actual)
4. Publish /cmd_vel with rotation to center target
```

### Safety Monitoring
```
Input: /scan

Check minimum range across all rays:
if (min_distance < EMERGENCY_THRESHOLD):
    Publish emergency stop to hardware
    Log warning
```

## Parameters

| Param | Type | Default | Purpose |
|-------|------|---------|---------|
| `safe_distance` | float | 0.3 m | Min distance before avoidance activates |
| `emergency_distance` | float | 0.15 m | Min distance before emergency stop |
| `linear_velocity_limit` | float | 0.1 m/s | Max forward speed during avoidance |
| `angular_velocity_limit` | float | 0.5 rad/s | Max rotation during avoidance |
| `scan_angle_min` | float | -180° | LiDAR FOV left edge |
| `scan_angle_max` | float | +180° | LiDAR FOV right edge |

## ROS2 Topics

### Subscriptions
| Topic | Type | Purpose |
|-------|------|---------|
| `/scan` | sensor_msgs/LaserScan | 2D LiDAR rays (from yahboomcar_base_node) |
| `/cmd_vel_input` | geometry_msgs/Twist | Desired motion (from teleop or navigator) |

### Publications
| Topic | Type | Purpose |
|-------|------|---------|
| `/cmd_vel` | geometry_msgs/Twist | Safe motion (obstacles already avoided) |
| `/emergency_stop` | std_msgs/Bool | High-priority safety signal |
| `/obstacle_warning` | std_msgs/String | JSON log of nearby obstacles |

## Laser Scanner Hardware

### Typical Setup
- **Model**: LDS-01 or similar 2D rotating LiDAR
- **Range**: 0.12–3.5 m (depends on object reflectivity)
- **Resolution**: ~360 rays per revolution (1° angular resolution)
- **Update Rate**: 5 Hz (ROS2 publishes at `/scan`)
- **Frame**: `laser_link` (TF mounted on robot)

### TF Frame Tree
```
base_link
    └→ laser_link (static offset: x=0.0435, z=0.11 m)
```

## Integration

### With Cartographer SLAM
- Avoidance node runs independently of SLAM
- Both read `/scan` topic (no conflict)
- SLAM uses `/scan` for localization; avoidance for safety
- Safe to run both simultaneously

### With Joy Teleop
```
Joy Controller
    ↓
clawbot_joy_teleop.py → /cmd_vel_input
    ↓
laser_Avoidance_a1_X3.py → /cmd_vel (safe motion)
    ↓
Wheels
```

### Launch Sequence
```bash
# Terminal 1: LiDAR driver (base node)
ROS_DOMAIN_ID=28 ros2 launch yahboomcar_base_node bringup.launch.py

# Terminal 2: Avoidance
ROS_DOMAIN_ID=28 ros2 launch yahboomcar_laser laser_Avoidance_a1_X3.launch.py

# Terminal 3: Joy teleop (optional)
ROS_DOMAIN_ID=28 ros2 launch joy_teleop joy_teleop_launch.py
```

## Known Limitations

- **2D Only**: Cannot detect obstacles above/below plane (use depth camera for 3D)
- **Reflectivity**: Dark matte objects → shorter effective range
- **Glass/Mirrors**: Reflections can cause false detections
- **Speed**: Response latency ~100–200 ms (scan update + processing)
- **Narrow Doorways**: May not fit through gaps < 0.5 m (no side collision check)

## Testing

### Verify Scan Reception
```bash
ROS_DOMAIN_ID=28 ros2 topic echo /scan --once
```

### Test Avoidance Live
```bash
ROS_DOMAIN_ID=28 ros2 launch yahboomcar_laser laser_Avoidance_a1_X3.launch.py

# In another terminal, send motion command:
ros2 topic pub /cmd_vel_input geometry_msgs/Twist \
  "{linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"

# Move obstacle in front of robot; should see /cmd_vel reduce to 0
ros2 topic echo /cmd_vel --once
```

### Record Avoidance Behavior (bag)
```bash
ros2 bag record /scan /cmd_vel_input /cmd_vel -o avoidance_test
```

## Future Work

- [ ] 3D obstacle detection (RGB-D camera fusion)
- [ ] Costmap-based navigation (instead of reactive)
- [ ] Multi-target tracking
- [ ] Predict moving obstacles (Kalman filtering)
- [ ] Dynamic parameter tuning via ROS2 parameters server

## Files Layout

```
yahboomcar_laser/
├── yahboomcar_laser/
│   ├── laser_Avoidance_a1_X3.py ⭐
│   ├── laser_Tracker_a1_X3.py
│   ├── laser_Warning_a1_X3.py
│   ├── common.py
│   └── __init__.py
├── launch/
│   ├── laser_Avoidance_a1_X3.launch.py
│   ├── laser_Tracker_a1_X3.launch.py
│   └── laser_Warning_a1_X3.launch.py
├── setup.py
├── package.xml
└── README.md (this file)
```

**Status**: ✅ Operational. Avoidance verified in test environment.

**Maintainer**: Yahboom (base), clawbot team (X3 adaptations)
