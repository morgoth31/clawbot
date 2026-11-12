---
type: ROS2 Node
title: "Bridge Node -- Noeud ROS2 (rclpy)"
description: Noeud ROS2 qui traduit les tool calls en appels HTTP vers le hardware_service (port 8001) et publie sur les topics ROS2.
status: stable
tags: [ros2, rclpy, node, bridge]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:15:00Z
sources:
  - id: bridge-node-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/ros2_llm_bridge/bridge_node.py
    title: bridge_node.py
    author: human:jetson
    last_modified: 2026-02-28
---

# Bridge Node

## Role

Le BridgeNode est un noeud ROS2 (rclpy) qui sert de traducteur entre les
appels de fonction de l'API et le hardware_service (port 8001).

## Topics ROS2

| Direction | Topic | Type | Usage |
|-----------|-------|------|-------|
| Publisher | /cmd_vel | geometry_msgs/Twist | Commandes de vitesse (fallback stop) |
| Subscriber | (via hardware_service) | - | Toutes les lectures se font via HTTP |

## Communication

Le bridge_node ne communique PAS directement avec le hardware. Il passe par
le hardware_service via HTTP (httpx.AsyncClient, base_url=localhost:8001).

### Pourquoi HTTP et pas ROS2 direct?

1. Le hardware_service a acces exclusif au serial (/dev/myserial)
2. Le hardware_service implemente les safety limits (clamping, watchdog, LiDAR)
3. Le driver_node (Mcnamu_driver_X3) garde l'acces exclusive au serial
4. Le bridge tourne en Docker, le hardware_service sur le host

## Methodes (17 tools)

### Motion
- `execute_set_velocity(linear_x, linear_y, angular_z)` -> POST /motion
- `execute_stop()` -> POST /motion/stop (fallback: publish Twist() sur /cmd_vel)
- `execute_speak(text)` -> stub (TODO: TTS ROS2 service)

### Navigation
- `execute_navigate_to(target_x, target_y)` -> stub (TODO: Nav2 NavigateToPose)

### Vision
- `execute_capture_camera(camera)` -> GET /capture?camera=front&save=true
- `execute_analyze_scene()` -> capture front camera
- `execute_recognize_face()` -> capture front camera
- `execute_recognize_object()` -> capture front camera
- `execute_recognize_qrcode()` -> capture front camera

### Audio
- `execute_listen()` -> stub (TODO: STT service)

### Arm & Claw
- `execute_control_servo(servo_id, angle)` -> POST /servo
- `execute_control_arm(joints_array)` -> POST /arm
- `execute_control_claw(state)` -> POST /claw
- `execute_set_arm_pose(pose_id)` -> POST /arm/pose/{id}

### Peripherals
- `execute_beep(delay_ms)` -> POST /beep
- `execute_set_lamps(r, g, b)` -> POST /lamps
- `execute_get_battery_voltage()` -> GET /battery

## Safety

Le bridge_node ne bypass JAMAIS le hardware_service pour le mouvement.
Si le hardware_service est injoignable pour SetVelocity, l'erreur est retournee.
Pour Stop seulement, il fallback sur /cmd_vel (un Twist vide = arret immediat).