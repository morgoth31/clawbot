---
title: "ERR-2026-11-10-001 — aucune source de scan laser publiée"
date: "2026-11-10T06:13:59+08:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, ros2, scan, lidar, navigation]
status: validé
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
| Statut | clos le 2026-11-10 — diagnostic initial corrigé |
| Mitigation appliquée | `clawbot-lidar.service` créé et activé ; `/scan` publié à 10,15 Hz |

> **Correction du 2026-11-10T13:45+08:00.** La conclusion initiale de cette trace était fausse : elle
> affirmait qu'aucun lidar n'était installé et qu'aucun pilote n'existait. L'investigation a établi
> l'inverse — un **YDLIDAR TG30** est présent, sain, et son pilote est compilé. La cause réelle est
> qu'**aucune unité systemd ne lançait le pilote**. Les sections 1 à 3 sont conservées telles quelles
> pour garder la trace du raisonnement erroné ; la section 7 documente la correction.

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

## 6. Correction du 2026-11-10 — cause réelle et preuve

### 6.1 Ce qui a été mesuré

```
$ lsusb | grep -E "10c4|1a86"
Bus 001 Device 008: ID 10c4:ea60 Silicon Labs CP210x UART Bridge   → /dev/ttyUSB0
Bus 001 Device 007: ID 1a86:7523 QinHeng CH340 serial converter    → /dev/ttyUSB1 (carte de commande)

$ ls -l /dev/rplidar /dev/ydlidar
/dev/rplidar -> ttyUSB0
/dev/ydlidar -> ttyUSB0

$ cat /etc/udev/rules.d/ydlidar.rules
KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ... SYMLINK+="ydlidar"

$ grep RPLIDAR_TYPE ~/.bashrc
export RPLIDAR_TYPE=4ROS 		# a1, s2, 4ROS

$ grep -A5 "lidar_4ROS_launch" yahboomcar_nav/launch/laser_bringup_launch.py
lidar_4ROS_launch = IncludeLaunchDescription(... 'ydlidar_ros2_driver', 'ydlidar_raw_launch.py' ...)
```

Le modèle `4ROS` de la configuration n'est donc pas un RPLIDAR Slamtec mais un **YDLIDAR** piloté par
`ydlidar_ros2_driver`, présent dans `yahboomcar_ros2_ws/software/library_ws` (source **et** binaire
compilé : `install/ydlidar_ros2_driver/lib/ydlidar_ros2_driver/ydlidar_ros2_driver_node`).

### 6.2 Identification du capteur

```
$ ros2 launch ydlidar_ros2_driver ydlidar_raw_launch.py
[YDLIDAR] Connection established in [/dev/ydlidar][512000]:
Firmware version: 1.71
Hardware version: 1
Model: TG30
Serial: 2025041700100211
[YDLIDAR] Get Sample Rate: 20K
Current Scan Frequency: 10.000000Hz
Now YDLIDAR is scanning ......
```

### 6.3 Fonctionnement après déploiement

Unité créée : `services/clawbot-lidar.service`, active, `ROS_DOMAIN_ID=28`.

```
$ ros2 topic info /scan
Type: sensor_msgs/msg/LaserScan     Publisher count: 1

$ ros2 topic hz /scan
average rate: 10.154

$ ros2 topic echo --once /scan --field ranges
[0.0, ..., 0.648, 0.645, 0.671, ..., 7.372, 7.396, ...]
```

Les trois conditions de clôture de la section 5 sont satisfaites : topic présent, cadence non nulle,
un éditeur.

### 6.4 Pourquoi le diagnostic initial s'est trompé

| Erreur de raisonnement | Ce qui l'a corrigée |
|---|---|
| « aucun paquet lidar installé » conclu depuis `ls /opt/ros/humble/share` | le pilote est dans un second espace de travail, `software/library_ws`, jamais inspecté |
| « rien sur `/dev/ttyUSB0` » conclu d'une lecture passive | un YDLIDAR n'émet qu'après commande ; 512 000 Bd n'était même pas testé |
| « aucun nœud lidar » conclu depuis le graphe | le graphe ne montre que ce qui **tourne** : une unité absente ne laisse aucune trace dans le graphe |

Règle retenue : **l'absence d'un topic ne prouve pas l'absence du matériel**. Avant de conclure, il
faut lancer le `launch` du constructeur et lire ce que le pilote annonce.

## 7. Reste ouvert

| Point | État |
|---|---|
| `/scan` publié | résolu — 10,15 Hz, `frame_id: laser` |
| TF `base_link → laser` | **non fourni** : `base_link` n'existe pas dans l'arbre ([[ERR-2026-11-10-003_arbre_tf_incomplet]]) |
| Navigation autonome | toujours bloquée par l'absence de `odom`/`map` et de pile de localisation déployée ([[ros2_nav_stack]]) |

## 8. Voir aussi

- Chaîne de navigation dépendante de ce topic : [[ros2_nav_stack]]
- Graphe complet et topics absents : [[ros2_graph_clawbot]]
- Journal de la session : [[2026-11-10_bootstrap_knowledge_base]]
- État des nœuds et services : [[etat_noeuds_et_services]]
- BOM logicielle (pilote YDLIDAR) : [[bom_logiciel]]
