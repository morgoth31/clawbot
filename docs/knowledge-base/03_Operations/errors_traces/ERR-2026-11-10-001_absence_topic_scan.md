---
title: "ERR-2026-11-10-001 — aucune source de scan laser publiée"
date: "2026-11-10T06:13:59+08:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, ros2, scan, lidar, navigation]
status: ouvert
---

# ERR-2026-11-10-001 — aucune source de scan laser publiée

| Champ | Valeur |
|---|---|
| Identifiant | `ERR-2026-11-10-001` |
| Horodatage de détection | 2026-11-10T06:14:30+08:00 (CST) |
| Domaine ROS 2 | 28 |
| Topic concerné | `/scan` (absent), `/scan_raw` (absent) |
| Composant lié | [[ros2_nav_stack]], [[ros2_graph_clawbot]] |
| Gravité d'exploitation | Blocage de la navigation fondée sur un balayage laser |
| Statut | ouvert |
| Mitigation appliquée | Aucune modification de la pile en exécution |

## 1. Nature de l'échec

Le topic de balayage laser n'existe pas dans le graphe ROS 2 du robot : `ros2 topic list -t` ne retourne ni `/scan` ni `/scan_raw`. Aucun nœud de télémétrie laser n'est enregistré (`ros2 node list` : 7 nœuds, aucun pilote de lidar). Aucun paquet de pilote de lidar n'est installé dans la distribution (`ls /opt/ros/humble/share | grep -iE 'lidar|rplidar|ydlidar|sllidar'` → aucune sortie).

## 2. Preuves

```
$ export ROS_DOMAIN_ID=28 && source /opt/ros/humble/setup.bash
$ ros2 topic list -t
/Buzzer [std_msgs/msg/Bool]
/RGBLight [std_msgs/msg/Int32]
/camera/color/camera_info [sensor_msgs/msg/CameraInfo]
/camera/color/image_raw [sensor_msgs/msg/Image]
/camera/depth/camera_info [sensor_msgs/msg/CameraInfo]
/camera/depth/image_raw [sensor_msgs/msg/Image]
/camera/depth/points [sensor_msgs/msg/PointCloud2]
/camera/detection_image [sensor_msgs/msg/CompressedImage]
/camera/ir/camera_info [sensor_msgs/msg/CameraInfo]
/camera/ir/image_raw [sensor_msgs/msg/Image]
/client_count [std_msgs/msg/Int32]
/cmd_vel [geometry_msgs/msg/Twist]
/connected_clients [rosbridge_msgs/msg/ConnectedClients]
/detections [std_msgs/msg/String]
/edition [std_msgs/msg/Float32]
/imu/data_raw [sensor_msgs/msg/Imu]
/imu/mag [sensor_msgs/msg/MagneticField]
/joint_states [sensor_msgs/msg/JointState]
/map [nav_msgs/msg/OccupancyGrid]
/parameter_events [rcl_interfaces/msg/ParameterEvent]
/rosout [rcl_interfaces/msg/Log]
/servo_ctrl [std_msgs/msg/Int32MultiArray]
/tf [tf2_msgs/msg/TFMessage]
/tf_static [tf2_msgs/msg/TFMessage]
/vel_raw [geometry_msgs/msg/Twist]
/voltage [std_msgs/msg/Float32]
```

```
$ ros2 node list
/camera/camera
/driver_node
/hardware_service_node
/llm_bridge_node
/rosapi
/rosapi_params
/rosbridge_websocket
```

```
$ ls /opt/ros/humble/share | grep -iE "lidar|rplidar|ydlidar|sllidar"
(aucune sortie, code retour 1)
```

## 3. Éléments matériels présents mais non exploités

| Périphérique | Identité USB | État d'exploitation |
|---|---|---|
| `/dev/ttyUSB0` | `Silicon_Labs CP2102` (`10c4:ea60`) | Aucun nœud ROS 2 ne l'ouvre — usage : Donnée non disponible |
| `/dev/ttyUSB1` | `QinHeng CH340` (`1a86:7523`) | Réservé à la carte Rosmaster via `/dev/myserial` — [[rosmaster_x3_mcu]] |
| `can0` | Interface CAN | État `DOWN`, aucun trafic |

L'absence de lidar n'est pas compensée : la passerelle matérielle déclare `LIDAR_SAFETY_REQUIRED=false`, ce qui autorise le mouvement sans retour laser.

## 4. Actions de mitigation

| Horodatage | Action | Résultat mesuré |
|---|---|---|
| 2026-11-10T06:14:30+08:00 | Consignation de la trace, aucun redémarrage de service | Pile inchangée ; 8 unités toujours actives |

## 5. Conditions de clôture

La trace passe à `validé` lorsque les trois mesures suivantes réussissent :

1. `ros2 topic list -t | grep /scan` retourne une entrée de type `sensor_msgs/msg/LaserScan`.
2. `ros2 topic hz /scan` retourne une cadence non nulle.
3. `ros2 topic info /scan` retourne `Publisher count` ≥ 1.

## 6. Voir aussi

- Chaîne de navigation dépendante de ce topic : [[ros2_nav_stack]]
- Graphe complet et topics absents : [[ros2_graph_clawbot]]
- Journal de la session : [[2026-11-10_bootstrap_knowledge_base]]
