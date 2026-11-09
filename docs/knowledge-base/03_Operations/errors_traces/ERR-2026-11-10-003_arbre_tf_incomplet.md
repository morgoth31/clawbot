---
title: "ERR-2026-11-10-003 — arbre TF incomplet (base robot absente)"
date: "2026-11-10T06:14:06+08:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, ros2, tf, urdf, odometrie]
status: ouvert
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

## 3. Cadres présents et absents

| Cadre | Présent dans TF | Émetteur |
|---|---|---|
| `camera_link` | oui (racine) | `/camera/camera` |
| `camera_color_frame` | oui | `/camera/camera` |
| `camera_depth_frame` | oui | `/camera/camera` |
| `camera_color_optical_frame` | oui | `/camera/camera` |
| `camera_depth_optical_frame` | oui | `/camera/camera` |
| `base_link` | non | Donnée non disponible — aucun éditeur |
| `base_footprint` | non | Donnée non disponible — aucun éditeur |
| `odom` | non | Donnée non disponible — aucun éditeur ; `/odom` absent du graphe |
| `map` | non | Donnée non disponible — aucun éditeur ; `/map` sans éditeur |
| `imu_link` | non (cité comme `frame_id` de `/imu/data_raw`) | [[yahboomcar_bringup_driver_node]] publie le message mais aucune transformation correspondante n'est présente |

## 4. Actions de mitigation

| Horodatage | Action | Résultat mesuré |
|---|---|---|
| 2026-11-10T06:14:48+08:00 | Consignation ; aucun `robot_state_publisher` lancé pour ne pas modifier la pile en production | Arbre TF inchangé |

## 5. Conditions de clôture

La trace passe à `validé` lorsque les trois mesures suivantes réussissent :

1. `ros2 run tf2_ros tf2_echo odom base_link` retourne une transformation valide.
2. `ros2 run tf2_ros tf2_echo map odom` retourne une transformation valide.
3. `ros2 node list | grep robot_state_publisher` retourne un nœud actif.

## 6. Voir aussi

- Descriptif du châssis et des cadres attendus : [[rosmaster_x3_mcu]]
- Chaîne de navigation : [[ros2_nav_stack]]
- Graphe complet : [[ros2_graph_clawbot]]
