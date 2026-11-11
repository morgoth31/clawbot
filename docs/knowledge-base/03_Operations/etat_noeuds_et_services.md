---
title: "État des nœuds ROS 2 et des services systemd"
date: "2026-11-11T16:59:13+01:00"
author: "Hermes Agent"
tags: [operations, etat, ros2, systemd, services, noeuds]
status: actif
generated: true
---

# État des nœuds ROS 2 et des services systemd

Instantané relevé le 2026-11-11T16:59:13+01:00 sur le poste, domaine ROS 2 `28`. Cette page est un relevé, pas un engagement : elle est régénérée par `scripts/generate_status.py` et ne se modifie pas à la main.

## 1. Services systemd

| Unité | Rôle | État | Actif depuis |
|---|---|---|---|
| `clawbot-description.service` | Description du robot (/robot_description, TF) | active (running) | Wed 2026-11-11 16:47:50 CET |
| `ros2-driver-node.service` | Nœud de conduite (cmd_vel → série) | active (running) | Wed 2026-11-11 12:08:20 CET |
| `ros2-hardware-service.service` | Service matériel du pont C++ | active (running) | Tue 2026-11-10 19:49:25 CET |
| `ros2-llm-bridge-cpp.service` | Pont LLM historique (port 8000) | active (running) | Tue 2026-11-10 19:49:25 CET |
| `orbbec-camera.service` | Caméra Orbbec Astra Pro+ | active (running) | Wed 2026-11-11 16:54:53 CET |
| `clawbot-lidar.service` | Lidar YDLIDAR TG30 (/scan) | active (running) | Tue 2026-11-10 08:10:07 CET |
| `clawbot-arm-controller.service` | Contrôleur de trajectoire du bras (→ /servo_ctrl) | active (running) | Wed 2026-11-11 16:13:19 CET |
| `clawbot-move-group.service` | MoveIt 2 move_group (démarré à la demande) | inactive (dead) | n/a |
| `rosbridge.service` | Passerelle WebSocket (port 9090) | inactive (dead) | Tue 2026-11-10 19:55:27 CET |
| `yolo-inference.service` | Inférence YOLO (port 8003) | active (running) | Wed 2026-11-11 16:53:55 CET |
| `clawbot-wrist-camera.service` | Caméra du poignet dans ROS (/wrist_camera/image_raw) | active (running) | Wed 2026-11-11 16:55:50 CET |
| `clawbot-joy-teleop.service` | Téléopération manette | inactive (dead) | n/a |
| `clawbot-ekf.service` | Filtre EKF (/odom, TF odom -> base_link) | active (running) | Wed 2026-11-11 16:34:51 CET |
| `clawbot-nav2.service` | Navigation Nav2 sur carte (AMCL, waypoints) | active (running) | Wed 2026-11-11 16:34:51 CET |
| `clawbot-slam.service` | SLAM Toolbox (cartographie, concurrence Nav2) | inactive (dead) | Wed 2026-11-11 12:08:20 CET |
| `clawbot-safety-arbitrator.service` | Arbitre réflexe 20 Hz (/cmd_vel_safe) | active (running) | Wed 2026-11-11 16:34:51 CET |
| `clawbot-director.service` | Directeur S1 (/director/command) | active (running) | Wed 2026-11-11 16:34:51 CET |
| `clawbot-sentinel.service` | Sentinel S1 (attention, mots d'arrêt) | active (running) | Wed 2026-11-11 16:34:51 CET |
| `clawbot-health.service` | Test de santé des périphériques | inactive (dead) | n/a |
| `clawbot-docs.service` | Site de documentation (port 8080) | active (running) | Wed 2026-11-11 16:41:45 CET |

## 2. Graphe ROS 2

Nœuds visibles : **40** — topics : **80**.

| Nœud |
|---|
| `/amcl` |
| `/arm_trajectory_server` |
| `/behavior_server` |
| `/bt_navigator` |
| `/bt_navigator_navigate_through_poses_rclcpp_node` |
| `/bt_navigator_navigate_to_pose_rclcpp_node` |
| `/camera/camera` |
| `/controller_server` |
| `/director` |
| `/driver_node` |
| `/ekf_filter_node` |
| `/global_costmap/global_costmap` |
| `/hardware_service_node` |
| `/joint_state_publisher` |
| `/launch_ros_1598014` |
| `/launch_ros_2416507` |
| `/lifecycle_manager_localization` |
| `/lifecycle_manager_navigation` |
| `/llm_bridge_node` |
| `/local_costmap/local_costmap` |
| `/map_server` |
| `/nav2_container` |
| `/planner_server` |
| `/robot_state_publisher` |
| `/rviz` |
| `/safety_arbitrator` |
| `/sentinel` |
| `/smoother_server` |
| `/transform_listener_impl_635e4e28b5b0` |
| `/transform_listener_impl_aaaaf9326990` |
| `/transform_listener_impl_ffff480023f0` |
| `/transform_listener_impl_ffff50009690` |
| `/transform_listener_impl_ffff58002810` |
| `/transform_listener_impl_ffff64006af0` |
| `/transform_listener_impl_ffff70002530` |
| `/velocity_smoother` |
| `/waypoint_follower` |
| `/wrist_camera/camera` |
| `/ydlidar_ros2_driver_node` |
| `/yolo_source_camera` |

## 3. Santé des périphériques

Verdict **failed** en 7181 ms ([[llm2ros_health_test_specification]]).

| Périphérique | Requis | Verdict | Détail |
|---|---|---|---|
| `PER-01` camera couleur | oui | ok | — |
| `PER-02` camera profondeur | oui | degraded | — — HLT-E-RATE-LOW |
| `PER-03` centrale inertielle | oui | ok | — |
| `PER-04` carte de commande | oui | ok | — |
| `PER-05` batterie | oui | ok | — |
| `PER-06` lidar | oui | ok | — |
| `PER-07` manette | non | failed | aucune manette presente sur le bus d'entree — HLT-E-DEVICE-ABSENT |
| `PER-08` chaine de detection | non | ok | — |
| `PER-09` arbre TF | oui | failed | cadres absents : map — HLT-E-NODE-ABSENT |

## 4. Ressources du poste

| Mesure | Valeur |
|---|---|
| Charge (1 / 5 / 15 min) | 3.81 / 4.96 / 4.90 |
| Mémoire disponible | 8749 Mo sur 15655 Mo |
| Disque libre | 21.3 Go |
| Températures | cpu-thermal 58 °C, gpu-thermal 55 °C, cv0-thermal 53 °C, cv1-thermal 52 °C, cv2-thermal 49 °C, soc0-thermal 52 °C, soc1-thermal 51 °C, soc2-thermal 50 °C, tj-thermal 58 °C |
| Disponibilité du poste | 43 h 5 min |

## 5. Ce que cette page ne prouve pas

- Un service `active` ne garantit pas qu'un périphérique est présent : c'est le rôle du test de
  santé, qui l'a établi pour la manette ([[llm2ros_health_test_specification]]).
- Un nœud présent dans le graphe ne publie pas nécessairement à la bonne cadence : les mesures
  de cadence figurent dans le rapport de santé, section 3.
- Ces valeurs sont un instantané : elles ne remplacent pas une supervision continue.

## 6. Regénérer cette page

```bash
cd /home/jetson/clawbot
PYTHONPATH=$PWD python3 scripts/generate_status.py
```

## 7. Voir aussi

- [[systemd_robot_services]] — description des unités et de leurs dépendances
- [[ros2_graph_clawbot]] — graphe de référence et cadences nominales
- [[llm2ros_health_test_specification]] — ce qui est vérifié sur les périphériques
