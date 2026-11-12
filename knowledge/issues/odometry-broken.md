---
type: Known Issue
title: "Odometrie Cassee -- /odom toujours 0,0,0"
description: L'odometrie du robot ne fonctionne pas a cause du conflit serial. Workaround: SLAM Cartographer LiDAR scan-matching.
status: stable
tags: [bug, odometry, slam, workaround]
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

# Odometrie Cassee

## Probleme
Le topic /odom publie toujours des valeurs nulles (0,0,0) car le driver_node
et le hardware_service entrent en conflit sur le port serie.

## Workaround Actuel
Utiliser Cartographer avec LiDAR scan-matching uniquement (ignorer /odom).
Le SLAM se base sur le scan LiDAR pour estimer la position, sans dependre
de l'odometrie des roues.

## Impact sur la Navigation
- **SLAM**: fonctionnel (Cartographer LiDAR-only)
- **Nav2**: non cable (NavigateTo est un stub)
- **Position estimee**: bonne en environnement structure, degradee en couloir long

## Solution Long Terme
1. Resoudre le [conflit serie](/issues/serial-conflict.md)
2. Restaurer l'odometrie
3. Fusion IMU + odom + LiDAR via EKF (robot_localization)
4. Cabler Nav2 NavigateToPose action server