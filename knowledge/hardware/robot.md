---
type: Hardware
title: "Robot Physique -- Yahboom X3 Plus"
description: Robot mobile Mecanum avec bras 5-DOF et pince. Base Jetson Orin.
status: stable
tags: [hardware, robot, yahboom, mecanum]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:25:00Z
sources:
  - id: codebase-map
    resource: file:///home/jetson/clawbot/CODEBASE_MAP.md
    title: CODEBASE_MAP.md
    author: human:jetson
    last_modified: 2026-03-06
  - id: work-state
    resource: file:///home/jetson/clawbot/WORK_STATE.md
    title: WORK_STATE.md
    author: human:jetson
    last_modified: 2026-03-02
---

# Robot Physique -- Yahboom X3 Plus

## Specifications

### Base Mobile
- **Model**: Yahboom X3 Plus
- **Roues**: 4 roues Mecanum (omnidirectionnelles)
- **Mouvement**: forward/backward, lateral (left/right), rotation sur place
- **Driver**: Mcnamu_driver_X3 (ROS2 node)
- **Serial**: /dev/myserial -> ttyUSB0 (CH340), 115200 baud
- **Vitesse max**: 0.06 m/s linear, 0.25 rad/s angular (hard limit logiciel)

### Bras Manipulateur
- **DOF**: 5 axes + pince (6 servos total)
- **Servos**: IDs 1-6, plage 0-180 degres
- **Control**: /servo_ctrl topic (Int32MultiArray)
- **MoveIt2**: NON integre (planning manuel uniquement)

#### Servo Map
| ID | Role | Range |
|----|------|-------|
| 1 | Base rotation | 0-180 (centre=90) |
| 2 | Shoulder lift | 0-180 |
| 3 | Elbow reach | 0-180 |
| 4 | Wrist tilt (pitch) | 0-180 |
| 5 | Wrist rotate (roll) | 0-180 |
| 6 | Claw open/close | 0=open, 180=closed |

### Poses Predefinies
| ID | Nom | Description |
|----|-----|-------------|
| 1 | Anti-collision | Bras plie, safe pour navigation |
| 2 | Dance | Bras tendu horizontal |
| 3 | Line-tracking | Bras bas, camera vers avant/bas |

### Calculateur
- **Platform**: NVIDIA Jetson (kernel 5.15.148-tegra)
- **OS**: Ubuntu (ROS2 Humble)
- **Serial baudrate**: 115200

### Batterie
- **Type**: 3S LiPo
- **Plage**: 9.6V - 12.6V
- **Derniere lecture**: 12.2V (86%) au 2026-03-04

### Controleur
- **Nintendo Pro Controller**: USB-C fonctionnel
- **Bluetooth**: non fonctionnel (kernel 5.15.148-tegra manque HIDP socket)
- **Driver**: hid-nintendo DKMS v3.2