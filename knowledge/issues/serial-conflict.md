---
type: Known Issue
title: "Conflit Port Serie -- hardware_service vs driver_node"
description: hardware_service et driver_node reclamant /dev/myserial simultanement, causant une odometrie cassee.
status: stable
tags: [bug, serial, odometry, critical]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:35:00Z
sources:
  - id: codebase-map
    resource: file:///home/jetson/clawbot/CODEBASE_MAP.md
    title: CODEBASE_MAP.md
    author: human:jetson
    last_modified: 2026-03-06
---

# Conflit Port Serie

## Probleme
`hardware_service.py` et `yahboomcar_bringup/Mcnamu_driver_X3.py` ouvrent
tous les deux `/dev/myserial` (-> ttyUSB0, CH340, 115200 baud).

## Impact
- `/odom` publie toujours 0,0,0 quand les deux tournent
- L'odometrie est inutilisable pour la navigation autonome

## Workaround Actuel
Le hardware_service a ete modifie pour NE PAS acceder au serial directement.
Il communique uniquement via topics ROS2 (/cmd_vel, /servo_ctrl, etc.).
Le driver_node garde l'acces exclusif au serial.

## Solution Recommandee
1. **Mergir les drivers**: un seul processus accede au serial
2. **Ou**: hardware_service en mode "topics only" (actuel), driver_node fait tout le serial
3. Le bypass LIDAR_SAFETY_REQUIRED=false est active car le hardware_service
   ne peut pas lire le LiDAR directement sans risk de conflit