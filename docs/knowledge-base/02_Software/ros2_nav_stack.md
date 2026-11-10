---
title: "ros2_nav_stack — chaîne de navigation (état de déploiement)"
date: "2026-11-10T06:13:48+08:00"
author: "Hermes Agent"
tags: [software, ros2, navigation, nav2, slam, tf, anomalie]
status: ouvert
---

# `ros2_nav_stack` — chaîne de navigation (état de déploiement)

État de la chaîne de navigation autonome sur le Clawbot X3. Retour à l'[[index]] ; graphe général : [[ros2_graph_clawbot]].

## 1. Constat de déploiement

| Élément de la chaîne | État constaté | Preuve |
|---|---|---|
| Paquets `nav2_*` installés | 34 paquets sous `/opt/ros/humble/share` | `ls /opt/ros/humble/share \| grep -c '^nav2_'` → 34 |
| `nav2_bringup` | Installé | `ls /opt/ros/humble/share/nav2_bringup` |
| `slam_toolbox` | Installé | `ls /opt/ros/humble/share/slam_toolbox` |
| Nœuds `nav2_*` en exécution | 0 | `ros2 node list` (domaine 28) |
| Carte d'occupation `/map` | Aucun éditeur | `ros2 topic info /map` → `Publisher count: 0`, `Subscription count: 1` (2026-11-10 12:30 CET) |
| Source laser `/scan` | Présente, `10,114 Hz` | `ros2 topic hz /scan` (2026-11-10 12:30 CET) ; [[ydlidar_tg30]] |
| Odométrie `/odom` | Absent du graphe | `ros2 topic list` sans `/odom` |
| Base robot `base_link` dans TF | Présente depuis le 2026-11-10 11:22 CET, avec `imu_link`, `laser_link`, `camera_link` | `ros2 run tf2_ros tf2_echo base_link laser_link` ([[ERR-2026-11-10-003_arbre_tf_incomplet]]) |
| Paramètre de sécurité laser | `LIDAR_SAFETY_REQUIRED=false` | `systemctl cat ros2-hardware-service.service` |
| Paquet SLAM maison `yahboomcar_slam` | Compilé (exécutable `pointcloud_mapping`) | `colcon build --packages-select yahboomcar_slam` ([[ERR-2026-11-10-008_paquet_opencv_incomplet]]) |

Conclusion factuelle : la chaîne de navigation est installée, deux de ses quatre prérequis d'entrée sont désormais satisfaits (`/scan` à 10,1 Hz et l'arbre TF de base), mais la pile n'est pas déployée : aucun nœud `nav2_*` actif, pas d'`/odom`, pas de TF `map → odom`, pas d'éditeur de `/map` au 2026-11-10 12:30 CET.

## 2. Conditions d'activation vérifiables

| Condition | État | Vérification |
|---|---|---|
| `/scan` publié et cadencé | Satisfaite (`10,114 Hz`) | `ros2 topic hz /scan` |
| `/odom` publié | Non satisfaite | `ros2 topic list` sans `/odom` |
| TF `odom → base_link` | Non satisfaite | `ros2 run tf2_ros tf2_echo odom base_link` |
| TF `map → odom` | Non satisfaite | idem |
| Carte `/map` servie | Non satisfaite | `ros2 topic info /map` → 0 éditeur |
| URDF chargé (`robot_state_publisher`) | Satisfaite depuis le 2026-11-10 11:39 CET | `ros2 node list` → `/robot_state_publisher` |

## 3. Mitigation appliquée

| Horodatage | Action | Résultat |
|---|---|---|
| 2026-11-10 06:15 CST | Aucune modification appliquée à la pile en exécution | État inchangé, anomalie consignée sous [[ERR-2026-11-10-001_absence_topic_scan]] et [[ERR-2026-11-10-003_arbre_tf_incomplet]] |
| 2026-11-10 13:55 CST | Déploiement de `clawbot-lidar.service` (TG30) | `/scan` publié à 10,1 Hz |
| 2026-11-10 11:39 CET | `clawbot-description.service` : `robot_state_publisher` diffuse l'URDF | `base_link`, `imu_link`, `laser_link`, `camera_link` dans TF |
| 2026-11-10 12:45 CET | Reconstruction du paquet SLAM maison contre OpenCV 4.5.4 (`/opt/opencv-4.5.4-dev`, identique à `cv_bridge`) | `yahboomcar_slam` compile, exécutable `pointcloud_mapping` produit |

## 4. Traces associées

| Trace | Objet | Statut |
|---|---|---|
| [[ERR-2026-11-10-001_absence_topic_scan]] | Absence de source de scan laser | corrigé |
| [[ERR-2026-11-10-003_arbre_tf_incomplet]] | TF sans odométrie ni carte | ouvert |
| [[ERR-2026-11-10-008_paquet_opencv_incomplet]] | OpenCV de développement incohérent, compilation SLAM | ouvert (contourné) |

## 5. Voir aussi

- Pilote châssis publiant `/vel_raw` sans `/odom` : [[yahboomcar_bringup_driver_node]]
- Capteur de profondeur exploitable comme source de substitution : [[orbbec_astra_pro_plus]]
- Supervision des services : [[systemd_robot_services]]
