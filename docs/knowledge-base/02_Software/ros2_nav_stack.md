---
title: "ros2_nav_stack — chaîne de navigation (état de déploiement)"
date: "2026-11-10T06:13:48+08:00"
author: "Hermes Agent"
tags: [software, ros2, navigation, nav2, slam, tf, anomalie]
status: validé
---

# `ros2_nav_stack` — chaîne de navigation (état de déploiement)

État de la chaîne de navigation autonome sur le Clawbot X3. Retour à l'[[index]] ; graphe général : [[ros2_graph_clawbot]].

## 1. Constat de déploiement

| Élément de la chaîne | État constaté | Preuve |
|---|---|---|
| Paquets `nav2_*` installés | 34 paquets sous `/opt/ros/humble/share` | `ls /opt/ros/humble/share \| grep -c '^nav2_'` → 34 |
| `nav2_bringup` | Installé | `ls /opt/ros/humble/share/nav2_bringup` |
| `slam_toolbox` | Installé | `ls /opt/ros/humble/share/slam_toolbox` |
| Nœuds `nav2_*` en exécution | 12 nœuds actifs depuis le 2026-11-11 16:03 CET | `ros2 node list` (domaine 28) : `amcl`, `bt_navigator`, `controller_server`, `planner_server`, `map_server`, `smoother_server`, `behavior_server`, `velocity_smoother`, `waypoint_follower`, deux `lifecycle_manager`, `nav2_container` |
| Carte d'occupation `/map` | Servie par `map_server`, 177 × 80 cellules à 0,05 m | `ros2 topic echo /global_costmap/costmap --field info` → `width: 177`, `height: 80` (2026-11-11 16:05 CET) |
| Source laser `/scan` | Présente, `10,114 Hz` | `ros2 topic hz /scan` (2026-11-10 12:30 CET) ; [[ydlidar_tg30]] |
| Odométrie `/odom` | Publiée à 10,0 Hz par `ekf_filter_node` (`clawbot-ekf.service`), TF `odom → base_link` | `ros2 topic hz /odom` → 10,001 Hz ; `tf2_echo odom base_link` (2026-11-11 16:01 CET) |
| Base robot `base_link` dans TF | Présente, avec `imu_link`, `laser_link`, `camera_link` ; chaîne complète `map → odom → base_link → laser_link` depuis le 2026-11-11 16:03 CET | `tf2_echo map base_link` → translation `[1.500, −0.300, 0.000]` ; `tf2_echo base_link laser_link` → `[0.105, 0.000, 0.032]` ([[ERR-2026-11-10-003_arbre_tf_incomplet]]) |
| Paramètre de sécurité laser | `LIDAR_SAFETY_REQUIRED=false` | `systemctl cat ros2-hardware-service.service` |
| Paquet SLAM maison `yahboomcar_slam` | Compilé (exécutable `pointcloud_mapping`) | `colcon build --packages-select yahboomcar_slam` ([[ERR-2026-11-10-008_paquet_opencv_incomplet]]) |

Conclusion factuelle : les six conditions d'activation sont satisfaites depuis le 2026-11-11 16:03 CET — `/scan` à 10,1 Hz, `/odom` à 10,0 Hz, `odom → base_link`, `map → odom` (AMCL), carte servie par `map_server`, URDF chargé. La pile est déployée par `clawbot-nav2.service` ; le catalogue de waypoints et la preuve de bout en bout sont décrits dans [[navigation_nav2_waypoints]].

## 2. Conditions d'activation vérifiables

| Condition | État | Vérification |
|---|---|---|
| `/scan` publié et cadencé | Satisfaite (`10,114 Hz`) | `ros2 topic hz /scan` |
| `/odom` publié | Satisfaite (10,0 Hz) | `ros2 topic hz /odom` |
| TF `odom → base_link` | Satisfaite | `tf2_echo odom base_link` → `[0.000, 0.000, 0.000]` au repos |
| TF `map → odom` | Satisfaite (AMCL) | `tf2_echo map base_link` |
| Carte `/map` servie | Satisfaite | `map_server` actif, costmap globale à 177 × 80 |
| URDF chargé (`robot_state_publisher`) | Satisfaite depuis le 2026-11-10 11:39 CET | `ros2 node list` → `/robot_state_publisher` |

## 3. Mitigation appliquée

| Horodatage | Action | Résultat |
|---|---|---|
| 2026-11-10 06:15 CST | Aucune modification appliquée à la pile en exécution | État inchangé, anomalie consignée sous [[ERR-2026-11-10-001_absence_topic_scan]] et [[ERR-2026-11-10-003_arbre_tf_incomplet]] |
| 2026-11-10 13:55 CST | Déploiement de `clawbot-lidar.service` (TG30) | `/scan` publié à 10,1 Hz |
| 2026-11-10 11:39 CET | `clawbot-description.service` : `robot_state_publisher` diffuse l'URDF | `base_link`, `imu_link`, `laser_link`, `camera_link` dans TF |
| 2026-11-10 12:45 CET | Reconstruction du paquet SLAM maison contre OpenCV 4.5.4 (`/opt/opencv-4.5.4-dev`, identique à `cv_bridge`) | `yahboomcar_slam` compile, exécutable `pointcloud_mapping` produit |
| 2026-11-11 15:56 CET | `clawbot-ekf.service` créé : EKF persistant, binaire du workspace constructeur | `/odom` 10,0 Hz, TF `odom → base_link` |
| 2026-11-11 16:03 CET | `clawbot-nav2.service` : `map_server` + AMCL + Nav2 sur la carte du catalogue | 12 nœuds actifs, costmap globale à 177 × 80 |

## 4. Traces associées

| Trace | Objet | Statut |
|---|---|---|
| [[ERR-2026-11-10-001_absence_topic_scan]] | Absence de source de scan laser | corrigé |
| [[ERR-2026-11-10-003_arbre_tf_incomplet]] | TF sans odométrie ni carte | corrigé le 2026-11-11 (EKF + AMCL) |
| [[ERR-2026-11-10-008_paquet_opencv_incomplet]] | OpenCV de développement incohérent, compilation SLAM | ouvert (contourné) |

## 5. Voir aussi

- Pilote châssis publiant `/vel_raw` sans `/odom` : [[yahboomcar_bringup_driver_node]]
- Capteur de profondeur exploitable comme source de substitution : [[orbbec_astra_pro_plus]]
- Supervision des services : [[systemd_robot_services]]
- Mise en service de la navigation et catalogue de waypoints : [[navigation_nav2_waypoints]]
