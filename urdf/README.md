# urdf

**Robot Model Definition & Transforms**

## Purpose
Contains the URDF (Unified Robot Description Format) model of the clawbot. Defines:
- Kinematic chain: base → arm joints (1-5) → gripper
- Sensor frames: LiDAR, cameras, IMU
- Collision meshes & visual geometry
- Transform tree (TF) for ROS2 pose tracking

## Files

- **`clawbot_X3.urdf`** (SolidWorks auto-exported)
  - 9 links: base_footprint, base_link, IMU, arm links (5), gripper
  - 8 joints: base_joint (fixed), arm 5-axis + gripper revolute, wheel joints
  - Inertia + collision meshes from Yahboom CAD models
  - Links to `/yahboomcar_description/meshes/` for STL geometry

- **`validate_urdf.py`**: URDF syntax checker
  - Validates XML, checks for missing frames/meshes, kinematic loops
  - Run: `python3 validate_urdf.py clawbot_X3.urdf`

## Kinematic Tree

```
base_footprint (origin, z=0)
    ↓ [fixed, z=0.0815]
base_link (chassis center)
    ├→ imu_link (IMU at base)
    ├→ laser_link (LiDAR, x=0.0435, z=0.11)
    ├→ camera_front_link (front camera)
    ├→ camera_claw_link (gripper-mounted camera)
    └→ shoulder_link (arm base)
        ↓ [revolute, joint_shoulder]
        arm_link_1 (shoulder)
        ↓ [revolute, joint_elbow]
        arm_link_2 (elbow)
        ↓ [revolute, joint_wrist_pitch]
        arm_link_3 (wrist pitch)
        ↓ [revolute, joint_wrist_roll]
        arm_link_4 (wrist roll)
        ↓ [revolute, joint_gripper_base]
        gripper_link (gripper base)
        ↓ [revolute, joint_gripper]
        gripper_finger_link (active claw)
```

## Static Transforms

These are **fixed offsets** applied by hardware_service.py:
- `base_footprint → base_link`: z=0.0815 m (ground clearance)
- `base_link → laser`: x=0.0435, z=0.11 (LiDAR mounting)
- Arm offsets: From URDF (SolidWorks export)
- Camera mounts: Inferred from CAD

## ROS2 Integration

### Published TF Tree
Broadcast by `robot_state_publisher` or `hardware_service.py`:
- **Fixed frames** (once at startup): base_footprint, base_link, sensor frames
- **Dynamic frames** (per joint command):
  - Arm joint positions from `/servo_status` topic
  - Base pose from `/odom` topic

### Mesh Assets
Path references: `package://yahboomcar_description/meshes/`
- Must exist in filesystem OR be configured in ROS2 package search path
- Format: STL binary (from SolidWorks CAD export)

### Parameter
- **ROS param**: `/robot_description` (URDF XML string)
  - Set by: `robot_state_publisher` or launch file
  - Used by: RViz, MoveIt2, Cartographer TF lookups

## Validation

```bash
cd /home/jetson/clawbot/urdf
python3 validate_urdf.py clawbot_X3.urdf
# Output: OK or error details
```

### Known Issues
- **Mesh paths**: STL files reference Yahboom package (may not be installed in your environment)
- **Floating base**: Uses base_footprint convention (fixed to ground), not actual floating base
- **Gripper**: Currently 1-DOF (open/close); no complex finger kinematics

## Future Work
- [ ] Add gripper finger spread (2-DOF gripper)
- [ ] Calibrate inertia tensors from CAD weights
- [ ] Add collision geometry for arm (currently only visual)
- [ ] MoveIt2 SRDF (kinematics + planning constraints)

## Usage in Launches

```python
# In ROS2 launch file:
robot_state_publisher = Node(
    package='robot_state_publisher',
    executable='robot_state_publisher',
    parameters=[{
        'robot_description': load_urdf_from_file('urdf/clawbot_X3.urdf')
    }]
)
```

**Status**: ✅ Validated. ~95% complete (gripper finger spread pending).

**Source**: Auto-exported from SolidWorks by Yahboom; hand-tuned transforms.
