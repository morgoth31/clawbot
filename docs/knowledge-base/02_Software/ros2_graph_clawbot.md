---
title: "Graphe ROS 2 actif — domaine 28 (Clawbot X3)"
date: "2026-11-10T06:13:38+08:00"
author: "Hermes Agent"
tags: [software, ros2, humble, topics, nodes, domain-28, graphe]
status: validé
---

# Graphe ROS 2 actif — domaine 28

État du graphe constaté le 2026-11-10 entre 06:12 et 06:15 CST, avec `ROS_DOMAIN_ID=28` et `source /opt/ros/humble/setup.bash`. Retour à l'[[index]].

Le domaine 28 est imposé par toutes les unités systemd du robot ([[systemd_robot_services]]) ; une session sans `ROS_DOMAIN_ID=28` ne voit aucun nœud (constat : `ros2 node list` vide).

## 1. Nœuds

| Nœud | Rôle constaté | Unité / source |
|---|---|---|
| `/camera/camera` | Pilote Orbbec Astra Pro+ ([[orbbec_astra_pro_plus]]) | `ros2-hardware-service.service` → `orbbec-camera.service` |
| `/driver_node` | Conduite châssis `Mcnamu_driver_X3` ([[yahboomcar_bringup_driver_node]]) | `ros2-driver-node.service` |
| `/hardware_service_node` | Passerelle matérielle (port HTTP 8001) | `ros2-hardware-service.service` |
| `/llm_bridge_node` | Pont LLM C++ (port HTTP 8000) | `ros2-llm-bridge-cpp.service` |
| `/rosbridge_websocket` | Pont WebSocket ROS 2 (port 9090) | `rosbridge.service` |
| `/rosapi` | API introspection rosbridge | `rosbridge.service` |
| `/rosapi_params` | API paramètres rosbridge | `rosbridge.service` |

Aucun nœud de navigation (`nav2_*`), de localisation, de SLAM ni de télémétrie laser n'est présent dans la liste ([[ros2_nav_stack]]).

## 2. Topics — éditeurs et cadences

| Topic | Type | Éditeurs | Abonnés | Cadence mesurée |
|---|---|---|---|---|
| `/voltage` | `std_msgs/msg/Float32` | 1 | 1 | 10,000 Hz |
| `/imu/data_raw` | `sensor_msgs/msg/Imu` | 1 | 1 | 9,999 Hz |
| `/camera/color/image_raw` | `sensor_msgs/msg/Image` | 1 | 0 | 20,109 Hz |
| `/camera/depth/image_raw` | `sensor_msgs/msg/Image` | 1 | 0 | 29,995 Hz |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | 2 | 1 | Donnée non disponible — aucun message reçu en 12 s (`ros2 topic echo --once`, timeout) |
| `/vel_raw` | `geometry_msgs/msg/Twist` | 1 | 1 | Donnée non disponible — cadence non instrumentée ; dernier message `linear.x = 0.0` |
| `/joint_states` | `sensor_msgs/msg/JointState` | 1 | 1 | Donnée non disponible — `ros2 topic hz` signale « does not appear to be published yet » |
| `/imu/mag` | `sensor_msgs/msg/MagneticField` | 1 | 1 | Donnée non disponible — cadence non instrumentée |
| `/edition` | `std_msgs/msg/Float32` | 1 | 1 | Donnée non disponible — cadence non instrumentée |
| `/Buzzer` | `std_msgs/msg/Bool` | 1 | 1 | Événementiel |
| `/RGBLight` | `std_msgs/msg/Int32` | 1 | 1 | Événementiel |
| `/servo_ctrl` | `std_msgs/msg/Int32MultiArray` | 1 | 1 | Événementiel |
| `/camera/color/camera_info` | `sensor_msgs/msg/CameraInfo` | 1 | 0 | Donnée non disponible — cadence non instrumentée |
| `/camera/depth/camera_info` | `sensor_msgs/msg/CameraInfo` | 1 | 0 | Donnée non disponible — cadence non instrumentée |
| `/camera/depth/points` | `sensor_msgs/msg/PointCloud2` | 1 | 0 | Donnée non disponible — cadence non instrumentée |
| `/camera/ir/image_raw` | `sensor_msgs/msg/Image` | 1 | 0 | Donnée non disponible — cadence non instrumentée |
| `/camera/ir/camera_info` | `sensor_msgs/msg/CameraInfo` | 1 | 0 | Donnée non disponible — cadence non instrumentée |
| `/tf` | `tf2_msgs/msg/TFMessage` | 1 | 0 | Donnée non disponible — cadence non instrumentée |
| `/tf_static` | `tf2_msgs/msg/TFMessage` | 1 | 0 | Événementiel (`transient_local`) |
| `/client_count` | `std_msgs/msg/Int32` | 0 | 0 | Donnée non disponible — éditeur absent |
| `/connected_clients` | `rosbridge_msgs/msg/ConnectedClients` | 0 | 0 | Donnée non disponible — éditeur absent |
| `/parameter_events` | `rcl_interfaces/msg/ParameterEvent` | 7 | 7 | Infrastructure rclpy |
| `/rosout` | `rcl_interfaces/msg/Log` | 7 | 7 | Infrastructure rclpy |

## 3. Topics déclarés sans éditeur actif

| Topic | Type | Éditeurs | Abonnés | Constat |
|---|---|---|---|---|
| `/detections` | `std_msgs/msg/String` | 0 | 1 | Aucun message reçu en 10 s (`ros2 topic echo --once`, timeout) |
| `/map` | `nav_msgs/msg/OccupancyGrid` | 0 | 1 | Aucune donnée : aucun éditeur enregistré |
| `/camera/detection_image` | `sensor_msgs/msg/CompressedImage` | 0 | 1 | Aucun message reçu en 8 s (`ros2 topic hz`, « does not appear to be published yet ») |

## 4. Topics absents du graphe

| Topic attendu | Constat | Code |
|---|---|---|
| `/scan`, `/scan_raw` | Absents de `ros2 topic list -t` | ROS2-TOPIC-ABSENT — [[ERR-2026-11-10-001_absence_topic_scan]] |
| `/odom`, `/odom_raw` | Absents de `ros2 topic list -t` | ROS2-TOPIC-ABSENT |
| `/battery_state` | Absent ; seule la tension brute `/voltage` existe | ROS2-TOPIC-ABSENT — [[batterie_principale]] |

## 5. Arbre TF

Frames présentes à la capture : `camera_link`, `camera_color_frame`, `camera_depth_frame`, `camera_color_optical_frame`, `camera_depth_optical_frame`.

Frames absentes : `base_link`, `base_footprint`, `odom`, `map`, `imu_link` (émis par le pilote comme `frame_id` de `/imu/data_raw` mais non présent dans `/tf` au moment de la capture).

`tf2_echo base_link camera_link` retourne :

```
Invalid frame ID "base_link" passed to canTransform argument target_frame - frame does not exist
```

Anomalie ouverte : [[ERR-2026-11-10-003_arbre_tf_incomplet]].

## 6. Voir aussi

- Détail du nœud de conduite : [[yahboomcar_bringup_driver_node]]
- Services supervisés : [[systemd_robot_services]]
- Plateforme de calcul : [[jetson_orin_nx]]
