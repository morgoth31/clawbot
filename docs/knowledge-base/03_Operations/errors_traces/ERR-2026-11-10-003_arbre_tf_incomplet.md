---
title: "ERR-2026-11-10-003 — arbre TF incomplet (base robot absente)"
date: "2026-11-10T06:14:06+08:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, ros2, tf, urdf, odometrie]
status: validé
---

# ERR-2026-11-10-003 — arbre TF incomplet (base robot absente)

| Champ | Valeur |
|---|---|
| Identifiant | `ERR-2026-11-10-003` |
| Horodatage de détection | 2026-11-10T06:14:48+08:00 (CST) |
| Domaine ROS 2 | 28 |
| Topics concernés | `/tf`, `/tf_static` |
| Composant lié | [[ros2_nav_stack]], [[orbbec_astra_pro_plus]] |
| Gravité d'exploitation | Blocage de la localisation et de la navigation |
| Statut | ouvert |
| Mitigation appliquée | Aucune ; aucun `robot_state_publisher` lancé |

## 1. Nature de l'échec

L'arbre TF ne contient que les cadres de la caméra. Les cadres de la base robot (`base_link`, `base_footprint`), de l'odométrie (`odom`) et de la carte (`map`) sont absents : toute transformation `base_link ↔ camera_link` échoue.

## 2. Preuves

```
$ export ROS_DOMAIN_ID=28 && source /opt/ros/humble/setup.bash
$ ros2 run tf2_ros tf2_echo base_link camera_link
[INFO] [1794262337.776479213] [tf2_echo]: Waiting for transform base_link ->  camera_link: Invalid frame ID "base_link" passed to canTransform argument target_frame - frame does not exist
[INFO] [1794262339.753142075] [tf2_echo]: Waiting for transform base_link ->  camera_link: Invalid frame ID "base_link" passed to canTransform argument target_frame - frame does not exist
```

```
$ ros2 topic echo --once /tf | grep -E "frame_id|child_frame_id"
    frame_id: camera_depth_frame
  child_frame_id: camera_color_frame
    frame_id: camera_link
  child_frame_id: camera_color_frame
    frame_id: camera_color_frame
  child_frame_id: camera_color_optical_frame
    frame_id: camera_depth_frame
  child_frame_id: camera_depth_optical_frame
    frame_id: camera_link
  child_frame_id: camera_depth_frame
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

Aucun nœud `robot_state_publisher`, `joint_state_publisher`, `static_transform_publisher` ni `slam_toolbox` n'apparaît dans la liste.

### 2.1 État au 2026-11-10 11:22 CET

Le graphe contient désormais les éditeurs de cadres, sans intervention sur la pile : `robot_state_publisher`, `joint_state_publisher`, `ydlidar_ros2_driver_node`, plus un lanceur `/launch_ros_1598014` dont l'origine (script de démarrage ou unité systemd) n'a pas été tracée. `ros2 node list` retourne alors :

```
/camera/camera
/driver_node
/hardware_service_node
/joint_state_publisher
/launch_ros_1598014
/llm_bridge_node
/robot_state_publisher
/rosapi
/rosapi_params
/rosbridge_websocket
/ydlidar_ros2_driver_node
```

## 3. Cadres présents et absents

| Cadre | Présent dans TF | Émetteur |
|---|---|---|
| `camera_link` | oui (racine) | `/camera/camera` |
| `camera_color_frame` | oui | `/camera/camera` |
| `camera_depth_frame` | oui | `/camera/camera` |
| `camera_color_optical_frame` | oui | `/camera/camera` |
| `camera_depth_optical_frame` | oui | `/camera/camera` |
| `base_link` | oui depuis le 2026-11-10 11:22 CET | `robot_state_publisher` — `base_footprint` → `base_link` (z = 0,076 m) |
| `base_footprint` | oui, idem | `robot_state_publisher` |
| `odom` | non | Donnée non disponible — aucun éditeur ; `/odom` absent du graphe |
| `map` | non | Donnée non disponible — aucun éditeur ; `/map` sans éditeur |
| `imu_link` | oui depuis le 2026-11-10 11:22 CET | `robot_state_publisher` — `base_link` → `imu_link`, translation `(0,001 m, 0,017 m, 0,0322 m)` |

## 4. Actions de mitigation

| Horodatage | Action | Résultat mesuré |
|---|---|---|
| 2026-11-10T06:14:48+08:00 | Consignation ; aucun `robot_state_publisher` lancé pour ne pas modifier la pile en production | Arbre TF inchangé |
| 2026-11-10T11:22:00+01:00 | Constat, sans action : `robot_state_publisher` et `joint_state_publisher` actifs, cadres `base_footprint`, `base_link`, `imu_link`, `camera_link`, `laser_link` publiés | `ros2 run tf2_ros tf2_echo base_link laser_link` retourne une transformation valide (`x = 0,105 m`, `z = 0,047 m`) ; `odom` et `map` toujours absents |

## 5. Conditions de clôture

La trace passe à `validé` lorsque les trois mesures suivantes réussissent :

1. `ros2 run tf2_ros tf2_echo odom base_link` retourne une transformation valide.
2. `ros2 run tf2_ros tf2_echo map odom` retourne une transformation valide.
3. `ros2 node list | grep robot_state_publisher` retourne un nœud actif.

## 5 bis. Clôture (2026-11-11 16:03 CET)

Les trois conditions sont satisfaites, mesurées en domaine 28 :

| Condition | Mesure | Résultat |
|---|---|---|
| `tf2_echo odom base_link` | `- Translation: [0.000, 0.000, 0.000]` (repos) | satisfaite, publiée par `ekf_filter_node` (`clawbot-ekf.service`) |
| `tf2_echo map odom` | chaîne `map → base_link` : `[1.500, -0.300, 0.000]` = pose initiale AMCL | satisfaite, publiée par `amcl` (`clawbot-nav2.service`) |
| `ros2 node list \| grep robot_state_publisher` | `/robot_state_publisher` actif | satisfaite |

Chaîne complète constatée : `map → odom → base_link → laser_link` (`[0.105, 0.000, 0.032]`).
Détail du déploiement : [[navigation_nav2_waypoints]].

## 6. Voir aussi

- Descriptif du châssis et des cadres attendus : [[rosmaster_x3_mcu]]
- Chaîne de navigation : [[ros2_nav_stack]]
- Graphe complet : [[ros2_graph_clawbot]]
