---
title: "2026-11-10 — Rebranchement de la caméra du bras : reprise USB et V4L2, index applicatif non aligné"
date: "2026-11-10T19:16:00+01:00"
author: "Hermes Agent"
tags: [operations, camera, uvc, usb, v4l2, bras, hotplug]
status: validé
---

# 2026-11-10 — Rebranchement de la caméra du bras

Geste opérateur : débranchement puis rebranchement de la caméra montée sur le bras manipulateur,
signalé à 19:09 CET. Relevé de reprise effectué dans la foulée, `ROS_DOMAIN_ID=28`.
Retour à l'[[index]] ; fiche du composant : [[camera_usb_bras]].

## 1. Ce que le noyau a enregistré

```text
$ journalctl -k --since "2026-11-10 18:55"
Nov 10 19:08:56 yahboom kernel: usb 1-2.2.1: USB disconnect, device number 6
Nov 10 19:08:58 yahboom kernel: usb 1-2.2.1: new high-speed USB device number 16 using tegra-xusb
Nov 10 19:08:58 yahboom kernel: usb 1-2.2.1: Found UVC 1.00 device USB 2.0 Camera (0c45:6340)
Nov 10 19:08:58 yahboom kernel: usb 1-2.2.1: 3:1: cannot get freq at ep 0x84   (× 3)
```

| Élément | Valeur | Source |
|---|---|---|
| Débranchement | 2026-11-10T19:08:56+01:00, device 6 sur `1-2.2.1` | `journalctl -k` |
| Rebranchement | 2026-11-10T19:08:58+01:00, nouveau numéro de device 16, même port | `journalctl -k` |
| Reconnaissance | UVC 1.00, `0c45:6340`, pilote `uvcvideo` lié aux interfaces 0 et 1 | `lsusb -t` |
| Lien `by-id` recréé | `…-video-index0` et `…-video-index1` à 19:08:58,800 | `ls -l --time-style=full-iso /dev/v4l/by-id/` |
| Avertissements `cannot get freq at ep 0x84` | identiques à ceux du démarrage ; endpoint audio, aucune incidence sur la capture vidéo | `journalctl -k` |

Le numéro de device est passé de 6 à 16 : c'est la preuve que le rebranchement a bien été vu par
l'USB, et non un périphérique resté en place.

## 2. État du périphérique après rebranchement

| Élément | Valeur | Source |
|---|---|---|
| Nœuds recréés | `/dev/video0`, `/dev/video1`, `/dev/media1` (horodatés 19:08) | `ls -l /dev/video*`, `ls -l /dev/media*` |
| Formats | `YUYV` uniquement, 640 × 480 à 30 / 25 / 20 / 15 / 10 / 5 i/s | `v4l2-ctl -d /dev/video0 --list-formats-ext` |
| Capture V4L2 | 3 images sans erreur | `v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=3` |
| Ouverture OpenCV | `isOpened: True`, 640 × 480 × 3, moyenne 142,1, image non uniforme | `cv2.VideoCapture(0)` |
| `/dev/video2` | **absent** | `ls /dev/video*` |

## 3. Ce qui n'est pas revenu : l'index applicatif

| Consommateur | Requête | Résultat mesuré (19:12 CET) |
|---|---|---|
| Service YOLO, caméra « claw » | `GET http://127.0.0.1:8003/detect_raw?camera=claw` | HTTP 500 `{"detail":"Camera error: Cannot open camera claw (index 2)"}` |
| Service YOLO, caméra « front » | `GET http://127.0.0.1:8003/detect_raw?camera=front` | HTTP 200 `{"detections":[],"detection_count":0,"inference_ms":656}` |
| Inventaire ROS 2 | `ros2 node list`, `ros2 topic list` | aucun nœud ni topic pour cette caméra |

La caméra est saine au niveau USB et V4L2 ; c'est la **configuration** (`CAMERA_CLAW_INDEX=2`,
schéma `'claw' → /dev/video2`) qui ne correspond à aucun périphérique présent. L'outil « claw » du
pont reste donc non fonctionnel, et l'outil « front » ouvre en réalité la caméra du bras.
Écart consigné en FON-02 et FON-07 de [[llm2ros_bridge_coherence_et_approche]].

## 4. Chaîne RGB-D : aucun effet

| Topic | Cadence mesurée après rebranchement | Source |
|---|---|---|
| `/camera/color/image_raw` | 20,06 Hz, âge du message 0,102 s, 640 × 480 `rgb8` | `ros2 topic hz`, abonnement `rclpy` |
| `/camera/depth/image_raw` | 29,99 Hz, âge du message 0,127 s, 640 × 480 `16UC1` | `ros2 topic hz`, abonnement `rclpy` |
| Fichiers ouverts par `/camera/camera` | `/dev/bus/usb/001/013` (`2bc5:060f`) et `/dev/bus/usb/001/015` (`2bc5:050f`) | `/proc/6287/fd` |

La caméra Astra n'a jamais été débranchée : elle consomme ses deux fonctions Orbbec directement en
USB (`usbfs`), sans passer par `/dev/video0`. Un flux RGB-D qui continue pendant qu'un nœud V4L
disparaît n'est donc pas une incohérence.

## 5. Actions appliquées

Aucune modification de configuration n'a été faite : la mesure ne permet pas de décider seule si
« claw » doit pointer sur l'index 0 (la caméra du bras) et si « front » doit être supprimé ou
réattribué à la RGB-D. Le choix appartient à l'opérateur.

## 6. Conditions de clôture vérifiables

1. `ls /dev/video*` liste le ou les périphériques attendus et le schéma du pont nomme un nœud présent.
2. `curl 'http://127.0.0.1:8003/detect_raw?camera=claw'` retourne HTTP 200 avec `inference_ms` renseigné.
3. `curl 'http://127.0.0.1:8003/detect_raw?camera=front'` ne renvoie plus l'image de la caméra du bras.
4. `python3 scripts/validate_okf.py` sans erreur sur les pages touchées.

## 7. Voir aussi

- Fiche du périphérique : [[camera_usb_bras]]
- Caméra RGB-D non concernée : [[orbbec_astra_pro_plus]]
- Écarts d'index et outils annoncés non fonctionnels : [[llm2ros_bridge_coherence_et_approche]]
- Superviseur et inventaire matériel : [[llm2ros_health_test_specification]]
- Support mécanique : [[bras_6dof]]
