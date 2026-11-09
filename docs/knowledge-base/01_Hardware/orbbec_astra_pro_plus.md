---
title: "Orbbec Astra Pro+ — caméra RGB-D"
date: "2026-11-10T06:12:57+08:00"
author: "Hermes Agent"
tags: [hardware, camera, rgbd, orbbec, astra, usb, depth]
status: validé
---

# Orbbec Astra Pro+ — caméra RGB-D

Capteur de perception principal. Retour à l'[[index]] ; graphe ROS 2 associé : [[ros2_graph_clawbot]].

## 1. Identification matérielle

| Élément | Valeur | Source |
|---|---|---|
| Capteur de profondeur | `ORBBEC Depth Sensor`, USB `2bc5:060f`, bus 001, device 013 | `lsusb` |
| Flux couleur (UVC) | `Orbbec 3D Technology International USB 2.0 Camera`, USB `2bc5:050f`, bus 001, device 015 | `lsusb` |
| Nœuds de périphérique | `/dev/video0`, `/dev/video1`, `/dev/media1` | `v4l2-ctl --list-devices` |
| Nom V4L2 du flux couleur | `USB 2.0 Camera: USB Camera (usb-3610000.usb-2.2.1)` | `v4l2-ctl --list-devices` |
| Interface du contrôleur | USB 2.0 (hub VIA Labs), lien `usb-3610000.usb` | `v4l2-ctl --list-devices` |

## 2. Flux ROS 2 publiés

Nœud : `/camera/camera`. Horodatage de capture : 2026-11-10 06:13 CST, `ROS_DOMAIN_ID=28`.

| Topic | Type | Résolution / encodage | Cadence mesurée | `frame_id` |
|---|---|---|---|---|
| `/camera/color/image_raw` | `sensor_msgs/msg/Image` | 640 × 480, `rgb8` | 20,1 Hz | `camera_color_optical_frame` |
| `/camera/depth/image_raw` | `sensor_msgs/msg/Image` | 640 × 480, `16UC1` | 30,0 Hz | `camera_depth_optical_frame` |
| `/camera/color/camera_info` | `sensor_msgs/msg/CameraInfo` | — | Donnée non disponible — cadence non instrumentée | `camera_color_optical_frame` |
| `/camera/depth/camera_info` | `sensor_msgs/msg/CameraInfo` | — | Donnée non disponible — cadence non instrumentée | `camera_depth_optical_frame` |
| `/camera/depth/points` | `sensor_msgs/msg/PointCloud2` | Donnée non disponible — dimensions non relevées | Donnée non disponible — cadence non instrumentée | Donnée non disponible |
| `/camera/ir/image_raw` | `sensor_msgs/msg/Image` | Donnée non disponible — dimensions non relevées | Donnée non disponible — cadence non instrumentée | Donnée non disponible |

Matrice intrinsèque couleur (`/camera/color/camera_info`, champ `k`) :

```
[546.04956055   0.          315.88653564
   0.          546.04956055  243.94358826
   0.            0.            1.        ]
```

soit `fx = fy = 546,05 px`, `cx = 315,89 px`, `cy = 243,94 px` ; distorsion : Donnée non disponible — champ `d` non relevé.

## 3. Services du pilote (`astra_camera_msgs`)

Services exposés par `/camera/camera` : `get_camera_info`, `get_camera_params`, `get_depth_auto_white_balance`, `get_depth_exposure`, `get_depth_gain`, `get_depth_supported_video_modes` (+ services de paramètres `describe_parameters`, `get_parameters`, `set_parameters`, `set_parameters_atomically`, `get_parameter_types`, `list_parameters`).

## 4. Configuration d'exécution

| Élément | Valeur | Source |
|---|---|---|
| Unité systemd | `orbbec-camera.service` (actif) | `systemctl list-units` |
| `ROS_DOMAIN_ID` | 28 | `systemctl cat orbbec-camera.service` |
| Profil DDS | `FASTRTPS_DEFAULT_PROFILES_FILE=/home/jetson/clawbot/fastdds_profile.xml` | `systemctl cat orbbec-camera.service` |
| Utilisateur | `jetson` | `systemctl cat orbbec-camera.service` |

## 5. Arbre TF émis

| Parent | Enfant |
|---|---|
| `camera_link` | `camera_color_frame`, `camera_depth_frame` |
| `camera_color_frame` | `camera_color_optical_frame` |
| `camera_depth_frame` | `camera_depth_optical_frame` |

Le cadre `camera_link` n'est rattaché à aucune base robot : l'arbre TF est incomplet ([[ERR-2026-11-10-003_arbre_tf_incomplet]]).

## 6. Voir aussi

- Chaîne de navigation (non déployée) : [[ros2_nav_stack]]
- Supervision : [[systemd_robot_services]]
