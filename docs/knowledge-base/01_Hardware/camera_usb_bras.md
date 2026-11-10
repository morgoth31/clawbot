---
title: "Caméra USB du bras — module UVC 0c45:6340"
date: "2026-11-10T19:15:00+01:00"
author: "Hermes Agent"
tags: [hardware, camera, uvc, v4l2, bras, claw, usb]
status: validé
---

# Caméra USB du bras — module UVC `0c45:6340`

Caméra montée sur le bras manipulateur ([[bras_6dof]]), distincte de la caméra RGB-D du châssis
([[orbbec_astra_pro_plus]]). C'est le périphérique que la configuration du pont nomme caméra
« claw » et que le service YOLO interroge sous le nom « claw ». Retour à l'[[index]].

## 1. Identification matérielle

| Élément | Valeur | Source |
|---|---|---|
| Couple USB | `0c45:6340`, constructeur « Microdia », produit « USB 2.0 Camera » | `lsusb`, 2026-11-10T19:12+01:00 |
| Port | bus 001, chemin `1-2.2.1`, high-speed 480 Mbit/s | `lsusb -t` |
| Fonctions exposées | interfaces 0 et 1 = Video (`uvcvideo`), interfaces 2 et 3 = Audio (`snd-usb-audio`) | `lsusb -t` |
| Nom `by-id` | `usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera-video-index0` → `video0` ; `…-video-index1` → `video1` | `ls -l /dev/v4l/by-id/` |
| Nœuds de périphérique | `/dev/video0`, `/dev/video1`, `/dev/media1` | `v4l2-ctl --list-devices` |
| Nom V4L2 | `USB 2.0 Camera: USB Camera (usb-3610000.usb-2.2.1)` | `v4l2-ctl --list-devices` |
| Second nœud | `/dev/video1` n'expose aucun format de capture (`VIDIOC_ENUM_FMT` sans entrée) | `v4l2-ctl -d /dev/video1 --list-formats-ext` |

Le nom `by-id` annonce un pont Sonix alors que `lsusb` annonce Microdia : deux libellés du noyau
pour le même couple. L'identité stable est `VID:PID` plus chemin de port USB, jamais `/dev/videoN`,
dont la numérotation est recréée à chaque rebranchement (voir [[2026-11-10_rebranchement_camera_bras]]).

## 2. Ce que cette caméra n'est pas

| Constat | Mesure | Source |
|---|---|---|
| Elle n'alimente aucun topic de la caméra RGB-D | le nœud `/camera/camera` (PID 6287) tient ouverts `/dev/bus/usb/001/013` (`2bc5:060f`) et `/dev/bus/usb/001/015` (`2bc5:050f`) et **aucun** nœud V4L | `ls -l /proc/6287/fd`, `fuser /dev/bus/usb/001/*` |
| Le flux couleur Astra passe par `usbfs`, pas par `uvcvideo` | `lsusb -t` : `Dev 15` interfaces Video, `Driver=usbfs` ; seul `Dev 16` (`0c45:6340`) est tenu par `uvcvideo` | `lsusb -t` |
| Un flux RGB-D survit à son débranchement | débranchement du `0c45:6340` à 19:08:56, rebranchement à 19:08:58 ; `/camera/color/image_raw` mesuré à 20,06 Hz après coup | `journalctl -k`, `ros2 topic hz` |

La page [[orbbec_astra_pro_plus]] attribuait auparavant `/dev/video0` au flux couleur de l'Astra :
cette attribution est fausse et a été corrigée sur place.

## 3. Modes exposés

`v4l2-ctl -d /dev/video0 --list-formats-ext`, 2026-11-10T19:13+01:00 :

| Format | Résolutions | Cadences |
|---|---|---|
| `YUYV` 4:2:2 (seul format exposé) | 640 × 480, 352 × 288, 320 × 240, 176 × 144, 160 × 120 | 30 / 25 / 20 / 15 / 10 / 5 i/s pour chacune des cinq tailles |

Aucun format compressé (`MJPG`) n'est exposé : à 640 × 480 et 30 i/s le flux occupe
640 × 480 × 2 × 30 ≈ 18,4 Mo/s, sur un hub USB 2.0 partagé avec la carte de commande, le lidar et
la caméra RGB-D.

## 4. Flux ROS 2 publiés

**Aucun.** Cette caméra n'est consommée par aucun nœud ROS 2 :

| Vérification | Résultat | Source |
|---|---|---|
| Nœud tenant `/dev/video0` | aucun (`fuser -v /dev/video0` vide) | 2026-11-10T19:11+01:00 |
| Topic publié depuis ce périphérique | aucun ; `ros2 topic list` ne contient que les topics Astra et ceux du châssis | `ros2 topic list`, `ros2 topic info -v` |
| `frame_id` connu | Donnée non disponible — `ROS2-TOPIC-ABSENT`, aucun TF ne décrit cette caméra | `ros2 run tf2_ros tf2_echo base_link <frame>` |

Conséquence : elle est invisible pour le graphe ROS 2, pour la supervision (`etat_noeuds_et_services`)
et pour tout outil qui ne passe pas par OpenCV. La seule voie d'accès est l'index brut d'OpenCV.

## 5. Accès applicatif

Depuis le 2026-11-10 19:49 CET, les deux services interrogent l'index 0 pour la pince : l'index 2
n'existe pas et provoquait un HTTP 500.

| Consommateur | Configuration | Mesure après correction | Source |
|---|---|---|---|
| `yolo-inference.service` | `CAMERA_FRONT_INDEX=0`, `CAMERA_CLAW_INDEX=0` | `GET /detect_raw?camera=claw` → HTTP 200, inférence 279 ms | `curl http://127.0.0.1:8003/detect_raw?camera=claw` |
| `ros2-hardware-service.service` | idem (unités déployée et dépôt) | `GET /capture?camera=claw` → HTTP 200 | `curl http://127.0.0.1:8001/capture?camera=claw` |
| Schéma d'outil du pont C++ | annonce encore `'claw' (/dev/video2)` | `/dev/video2` reste absent : le schéma est faux, l'index réel est 0 | `tool_schemas.cpp:80` |

Conséquence assumée : `front` et `claw` désignent maintenant le **même** périphérique. La vue avant
du robot est la caméra RGB-D Astra ; elle n'est pas exposée en V4L et n'a donc pas d'index OpenCV.
Tant que les services ne lisent pas le topic `/camera/color/image_raw`, l'outil « front » renvoie
l'image de la caméra du bras — c'est inscrit en commentaire dans les deux unités systemd.

Écart consigné en FON-02 et FON-07 de [[llm2ros_bridge_coherence_et_approche]].

## 6. Preuves de fonctionnement

Relevé du 2026-11-10T19:12+01:00, après rebranchement :

| Preuve | Résultat | Commande |
|---|---|---|
| Capture V4L2 directe | 3 images capturées sans erreur | `v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=3` |
| Ouverture OpenCV | `isOpened: True`, image 640 × 480 × 3, moyenne 142,1 | `/home/jetson/yolov5_env/bin/python3` + `cv2.VideoCapture(0)` |
| Contenu de l'image | scène non uniforme, cadrage vers le haut (plafond et mur blancs, échelle à gauche) — vue différente de celle de l'Astra | capture `../../assets/captures/camera_bras_2026-11-10.png` |
| Accès par l'API de vision | `GET http://127.0.0.1:8003/detect_raw?camera=front` → `{"camera":"front","detections":[],"detection_count":0,"inference_ms":656}`, HTTP 200 | `curl` |

## 7. Limites constatées

- Aucun topic ROS 2 ni TF : la caméra n'est pas exploitable par la navigation, la cartographie ou un
  asservissement.
- Intrinsèques et distorsion : Donnée non disponible — aucune calibration (`/camera_info` inexistant
  pour ce périphérique).
- Les deux interfaces audio ne sont consommées par aucun service : Donnée non disponible — usage non
  défini.
- Le nom « front » de l'index 0 désigne en réalité cette caméra du bras ; la caméra avant du châssis
  est la RGB-D Astra, interrogée en ROS et non en OpenCV.

## 8. Voir aussi

- Support mécanique : [[bras_6dof]]
- Caméra RGB-D du châssis, à ne pas confondre : [[orbbec_astra_pro_plus]]
- Écart d'index et outils non fonctionnels : [[llm2ros_bridge_coherence_et_approche]]
- Journal du rebranchement du 2026-11-10 : [[2026-11-10_rebranchement_camera_bras]]
- Pont qui interroge la caméra : [[llm2ros_bridge]]
