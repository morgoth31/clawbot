---
title: "Orbbec Astra Pro+ — caméra RGB-D"
date: "2026-11-10T06:12:57+08:00"
author: "Hermes Agent"
tags: [hardware, camera, rgbd, orbbec, astra, usb, depth, uvc, calibration]
status: validé
---

# Orbbec Astra Pro+ — caméra RGB-D

Capteur de perception principal. Retour à l'[[index]] ; graphe ROS 2 associé : [[ros2_graph_clawbot]] ; référence constructeur : [[documentation_constructeur_yahboom]].

## 1. Identification matérielle

L'identité s'écrit avec le couple `VID:PID` et le nom `by-id`, jamais avec `/dev/videoN`, qui change au rebranchement.

| Élément | Valeur | Source |
|---|---|---|
| Capteur de profondeur | `ORBBEC Depth Sensor`, USB `2bc5:060f`, bus 001, device 013 | `lsusb` |
| Flux couleur (UVC) | `Orbbec 3D Technology International USB 2.0 Camera`, USB `2bc5:050f`, bus 001, device 015 | `lsusb` |
| Nom `by-id` du flux couleur | `usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera-video-index0` → `video0` | `ls -l /dev/v4l/by-id/` |
| Second nœud du flux couleur | `usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera-video-index1` → `video1` (métadonnées, aucun format de capture) | `ls -l /dev/v4l/by-id/`, `v4l2-ctl -d /dev/video1 --list-formats-ext` |
| Nœuds de périphérique | `/dev/video0`, `/dev/video1`, `/dev/media1` | `v4l2-ctl --list-devices` |
| Nom V4L2 du flux couleur | `USB 2.0 Camera: USB Camera (usb-3610000.usb-2.2.1)` | `v4l2-ctl --list-devices` |
| Interface du contrôleur | USB 2.0 (hub VIA Labs), lien `usb-3610000.usb` | `v4l2-ctl --list-devices` |

Le nom `by-id` annonce un pont UVC **Sonix** alors que `lsusb` annonce Orbbec : les deux fonctions (couleur UVC et profondeur propriétaire) n'ont pas le même couple `VID:PID`, ce qui interdit d'identifier la caméra par un seul des deux.

## 2. Modes exposés par le flux couleur

`v4l2-ctl -d /dev/video0 --list-formats-ext`, 2026-11-10 11:35 CET :

| Format | Résolutions | Cadences |
|---|---|---|
| `YUYV` 4:2:2 (seul format exposé) | 640 × 480, 352 × 288, 320 × 240, 176 × 144, 160 × 120 | 640 × 480, 352 × 288 et 320 × 240 à 30 / 25 / 20 / 15 / 10 / 5 i/s ; autres tailles `Donnée non disponible — non détaillées` |

Aucun format compressé (`MJPG`) n'est exposé sur ce nœud : le flux couleur occupe donc 640 × 480 × 2 octets × 20 i/s ≈ 12,3 Mo/s sur un lien USB 2.0 partagé avec la profondeur, ce qui explique que la cadence couleur mesurée (20,1 Hz) soit inférieure à la profondeur (30,0 Hz).

## 3. Flux ROS 2 publiés

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

## 4. Services du pilote (`astra_camera_msgs`)

Services exposés par `/camera/camera` : `get_camera_info`, `get_camera_params`, `get_depth_auto_white_balance`, `get_depth_exposure`, `get_depth_gain`, `get_depth_supported_video_modes` (+ services de paramètres `describe_parameters`, `get_parameters`, `set_parameters`, `set_parameters_atomically`, `get_parameter_types`, `list_parameters`).

## 5. Configuration d'exécution

| Élément | Valeur | Source |
|---|---|---|
| Unité systemd | `orbbec-camera.service` (actif) | `systemctl list-units` |
| `ROS_DOMAIN_ID` | 28 | `systemctl cat orbbec-camera.service` |
| Profil DDS | `FASTRTPS_DEFAULT_PROFILES_FILE=/home/jetson/clawbot/fastdds_profile.xml` | `systemctl cat orbbec-camera.service` |
| Utilisateur | `jetson` | `systemctl cat orbbec-camera.service` |
| Paquet pilote | `astra_camera` 1.1.0 (`astra_camera_msgs` 1.0.1), `ros2_astra_camera` | `~/yahboomcar_ros2_ws/software/library_ws/src/ros2_astra_camera/*/package.xml` |
| Lanceur | `ros2 launch astra_camera astro_pro_plus.launch.xml` | `systemctl cat orbbec-camera.service` |
| Reprise après échec | `Restart=on-failure`, `RestartSec=10`, `StartLimitBurst=3` / 60 s | idem |

Le pilote utilisé est la version ROS 2 (`ros2_astra_camera`), alors que les cours constructeur documentent le pilote ROS 1 `ros_astra_camera` (`11.Depth camera course/01.How to use the Astra camera`). Le constructeur y impose l'exécution du script `create_udev_rules` du paquet `astra_camera` : sur ce poste, la règle n'est pas nécessaire, la caméra est découverte sans elle (deux nœuds présents dans `lsusb` et flux publiés). Si les droits `video*` deviennent insuffisants après une réinstallation, c'est le premier point à vérifier.

## 6. Arbre TF émis

| Parent | Enfant | Source |
|---|---|---|
| `base_link` | `camera_link` | `/tf_static`, translation `(-0,0436 m, 0,0 m, 0,4196 m)`, rotation identité — `ros2 run tf2_ros tf2_echo base_link camera_link` |
| `camera_link` | `camera_color_frame`, `camera_depth_frame` | `/tf_static` du pilote |
| `camera_color_frame` | `camera_color_optical_frame` | idem |
| `camera_depth_frame` | `camera_depth_optical_frame` | idem |

Le cadre `camera_link` est désormais rattaché à `base_link` par `robot_state_publisher` : la phrase « aucune base robot » de la première capture n'est plus exacte. `odom` et `map` restent absents, donc [[ERR-2026-11-10-003_arbre_tf_incomplet]] demeure ouverte.

## 7. Étalonnage

| Élément | État |
|---|---|
| Intrinsèques couleur | mesurées et publiées (voir §3) |
| Distorsion couleur | Donnée non disponible — champ `d` non relevé |
| Intrinsèques profondeur | Donnée non disponible — non relevées |
| Transformation profondeur → couleur (registration) | Donnée non disponible — non vérifiée |
| Procédure constructeur | `11.Depth camera course/02.Astra camera calibration` (ROS 1, `camera_calibration`, mires damier) ; non exécutée sur ce poste |

## 8. Conflit de port à connaître

Le cours constructeur `01.How to use the Astra camera` §1.4 fait démarrer `web_video_server` sur `http://<robot>:8080/` pour visualiser le flux dans un navigateur. **Le port 8080 est déjà occupé sur ce robot par le site de documentation** (`clawbot-docs.service`, `mkdocs serve`). Lancer `web_video_server` sans changer de port échoue ou masque la documentation ; utiliser `web_video_server` avec un autre port (`port:=8081`) et vérifier `ss -ltnp | grep 808`.

## 9. Limites constatées

- Portée de profondeur, précision et comportement en extérieur : aucune campagne de mesure, `Donnée non disponible`.
- Alignement profondeur/couleur non vérifié : un nuage coloré peut être décalé sans que rien ne le signale dans les topics.
- Le flux couleur est limité à `YUYV` sur ce nœud ; toute demande de `MJPG` échoue.

## 10. Voir aussi

- Chaîne de navigation (non déployée) : [[ros2_nav_stack]]
- Supervision : [[systemd_robot_services]]
- Lidar complémentaire : [[ydlidar_tg30]]
- Documentation constructeur : [[documentation_constructeur_yahboom]]
- Anomalie TF historique : [[ERR-2026-11-10-003_arbre_tf_incomplet]]
