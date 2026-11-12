---
type: Hardware
title: "URDF -- Modele Robot (9 links, 8 joints)"
description: Modele URDF du Clawbot: arbre TF base_footprint -> camera_link avec bras 5-DOF + pince.
status: stable
tags: [urdf, tf, robot-model]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:25:00Z
sources:
  - id: work-state
    resource: file:///home/jetson/clawbot/WORK_STATE.md
    title: WORK_STATE.md
    author: human:jetson
    last_modified: 2026-03-02
  - id: urdf-file
    resource: file:///home/jetson/clawbot/urdf/clawbot_X3.urdf
    title: clawbot_X3.urdf
    author: human:jetson
    last_modified: 2026-03-01
---

# URDF -- Modele Robot

## Fichier
- **Chemin**: `/home/jetson/clawbot/urdf/clawbot_X3.urdf`
- **Validation**: `validate_urdf.py` -- URDF valide
- **Note**: xacro upstream a un bug sur l'arg `ns` -> utiliser URDF statique

## Structure TF

```
base_footprint
  -> base_link (z=0.0815, static TF)
    -> roues (4x)
    -> arm_base_link
      -> shoulder_link (joint 1: base rotation)
        -> upper_arm_link (joint 2: shoulder)
          -> forearm_link (joint 3: elbow)
            -> wrist_link (joint 4: wrist tilt)
              -> hand_link (joint 5: wrist rotate)
                -> gripper_link (joint 6: claw)
                  -> camera_link (claw camera)
    -> front_camera_link (front camera, static)
```

## Links (9)
1. base_footprint (sol)
2. base_link (chassis)
3. arm_base_link
4. shoulder_link
5. upper_arm_link
6. forearm_link
7. wrist_link
8. hand_link
9. gripper_link (+ camera_link)

## Joints (8)
- 6 joints continus/revolute (servos 1-6)
- 2 joints fixes (base_footprint->base_link, cameras)

## TF Publishers
- **Static**: robot_state_publisher (URDF -> TF statiques)
- **Dynamic**: positions des joints publiees per /servo_status
- **Verification**: `ros2 run tf2_tools view_frames`