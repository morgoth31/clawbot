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
| Carte d'occupation `/map` | Aucun éditeur | `ros2 topic info /map` → `Publisher count: 0`, `Subscription count: 1` |
| Source laser `/scan` | Absent du graphe | `ros2 topic list -t` ([[ERR-2026-11-10-001_absence_topic_scan]]) |
| Odométrie `/odom` | Absent du graphe | `ros2 topic list -t` |
| Base robot `base_link` dans TF | Absente | `tf2_echo base_link camera_link` → `frame does not exist` ([[ERR-2026-11-10-003_arbre_tf_incomplet]]) |
| Paramètre de sécurité laser | `LIDAR_SAFETY_REQUIRED=false` | `systemctl cat ros2-hardware-service.service` |

Conclusion factuelle : la chaîne de navigation est installée mais non déployée. Aucun nœud de planification, de localisation ou de contrôle de trajectoire n'est actif ; les quatre prérequis d'entrée (`/scan`, `/odom`, TF `map→odom→base_link`, `/map`) sont absents du graphe au 2026-11-10 06:15 CST.

## 2. Conditions d'activation vérifiables

| Condition | État | Vérification |
|---|---|---|
| `/scan` publié et cadencé | Non satisfaite | `ros2 topic hz /scan` → topic absent |
| `/odom` publié | Non satisfaite | `ros2 topic list -t` sans `/odom` |
| TF `odom → base_link` | Non satisfaite | `ros2 run tf2_ros tf2_echo odom base_link` |
| TF `map → odom` | Non satisfaite | idem |
| Carte `/map` servie | Non satisfaite | `ros2 topic info /map` → 0 éditeur |
| URDF chargé (`robot_state_publisher`) | Non satisfaite | `ros2 node list` sans `robot_state_publisher` |

## 3. Mitigation appliquée

| Horodatage | Action | Résultat |
|---|---|---|
| 2026-11-10 06:15 CST | Aucune modification appliquée à la pile en exécution | État inchangé, anomalie consignée sous [[ERR-2026-11-10-001_absence_topic_scan]] et [[ERR-2026-11-10-003_arbre_tf_incomplet]] |

## 4. Traces associées

| Trace | Objet | Statut |
|---|---|---|
| [[ERR-2026-11-10-001_absence_topic_scan]] | Absence de source de scan laser | ouvert |
| [[ERR-2026-11-10-003_arbre_tf_incomplet]] | TF sans base robot ni odométrie | ouvert |

## 5. Voir aussi

- Pilote châssis publiant `/vel_raw` sans `/odom` : [[yahboomcar_bringup_driver_node]]
- Capteur de profondeur exploitable comme source de substitution : [[orbbec_astra_pro_plus]]
- Supervision des services : [[systemd_robot_services]]
