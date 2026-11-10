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
| Pilote du flux couleur | fonctions Video d'`usbfs`, **pas** `uvcvideo` : le nœud ouvre le périphérique USB en direct | `lsusb -t` (`Dev 15` → `Driver=usbfs`) |
| Fichiers tenus ouverts par le nœud | `/dev/bus/usb/001/013` et `/dev/bus/usb/001/015` | `ls -l /proc/6287/fd`, `fuser /dev/bus/usb/001/*` |
| Nœuds V4L associés | **aucun** : `/dev/video0`, `/dev/video1` et `/dev/media1` appartiennent à une autre caméra, `0c45:6340`, décrite dans [[camera_usb_bras]] | `v4l2-ctl --list-devices`, `lsusb -t` |
| Interface du contrôleur | bus 001, hub VIA Labs `2109:2817`, high-speed 480 Mbit/s | `lsusb -t` |

Deux couples coexistent donc sur le même capteur, et **aucun des deux n'est exposé en V4L** :
`2bc5:060f` pour la profondeur, `2bc5:050f` pour la couleur. Une page ou une sonde qui associe
`/dev/video0` ou le couple `0c45:6340` à cette caméra désigne en réalité la caméra du bras
([[camera_usb_bras]]). Le lien entre périphérique et topic se vérifie par les descripteurs ouverts
du nœud, jamais par le nom V4L2.

## 2. Mode négocié et cadence publiée

Le flux couleur n'étant pas exposé en V4L, `v4l2-ctl --list-formats-ext` ne peut pas l'énumérer :
la configuration se lit dans le journal du pilote et dans les messages publiés.

| Élément | Valeur | Source |
|---|---|---|
| Mode UVC négocié par le pilote | 640 × 480 à 30 i/s, `UVC_FRAME_FORMAT_MJPEG` | journal de `orbbec-camera.service` : `set uvc mode 640x480@30 format UVC_FRAME_FORMAT_MJPEG` |
| Encodage publié | `rgb8`, 640 × 480 | `/camera/color/image_raw` |
| Cadence publiée | 20,06 Hz (fenêtres de 22 et 43 messages) | `ros2 topic hz`, 2026-11-10T19:12+01:00 |
| Modes V4L2 énumérables | Donnée non disponible — `VIDIOC_ENUM_FMT` impossible sur un périphérique tenu par `usbfs` | `lsusb -t` |
| Débit occupé sur le lien USB | Donnée non disponible — non mesuré | — |

Le pilote négocie 30 i/s en MJPEG alors que le topic est publié à 20,06 Hz : l'écart est constaté,
son origine n'est pas établie (`Donnée non disponible`). Aucune mesure de débit ne permet d'attribuer
cet écart à la bande passante du lien USB 2.0.

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

Le cours constructeur `01.How to use the Astra camera` §1.4 fait démarrer `web_video_server` sur `http://<robot>:8080/` pour visualiser le flux dans un navigateur. **Le port 8080 est occupé par le site de documentation** (`clawbot-docs.service`) et 8081 par le tableau de bord `charles_dashboard`. Solution retenue : flux vidéo sur **8082**, port libre au relevé ; le site garde 8080. Détail de l'allocation et commandes : [[ports_reseau]].

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
