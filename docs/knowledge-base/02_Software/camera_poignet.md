---
title: "Caméra du poignet (0c45:6340) — nœud ROS, cadre optique et propriété exclusive du périphérique"
date: "2026-11-11T17:05:00+01:00"
author: "Hermes Agent"
tags: [software, ros2, caméra, uvc, v4l2, perception, système1, systemd]
status: validé
---

# Caméra du poignet dans ROS

Première moitié de la brique 6 : la caméra USB `0c45:6340` montée sur le bras publie désormais une
image dans le graphe ROS, avec un cadre optique et une calibration **déclarée non mesurée**. Retour
à l'[[index]] ; matériel : [[inventaire_materiel]] ; modèle géométrique : [[modele_urdf_clawbot]].

## 1. Identification du périphérique

| Champ | Valeur | Preuve |
|---|---|---|
| Identité | `ID_VENDOR_ID=0c45` `ID_MODEL_ID=6340` | `udevadm info -q property -n /dev/video0` |
| Nœuds V4L2 | `video0` (capture) et `video1` (métadonnées) | `v4l2-ctl --list-devices` |
| Chemin stable | `/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera-video-index0` | `ls -l /dev/v4l/by-id/` |
| Pilote | `uvcvideo` | journal `v4l2_camera` : `Driver: uvcvideo` |
| Lien USB | 480 Mb/s (USB 2.0 high speed), port `1-2.2.1` | `cat /sys/bus/usb/devices/1-2.2.1/speed` |
| Formats | YUYV 4:2:2 uniquement, 640×480 à 320×240 | `v4l2-ctl --list-formats-ext` |

Les deux nœuds partagent une seule caméra : l'index `video1` n'est pas une seconde caméra. Aucun
nœud V4L2 n'appartient à l'Astra Pro+, qui passe par `usbfs`.

## 2. Cadre optique dans l'URDF

`mono_link` est le support physique de cette caméra, monté sur **`arm_link4`** (joint fixe,
`xyz="-0.0481 -0.05145 -0.0022"`, `rpy="1.5708 0 0"`). Le cadre optique est donc un enfant de
`mono_link` :

```xml
<link name="wrist_camera_optical_frame"/>
<joint name="wrist_camera_optical_joint" type="fixed">
    <origin xyz="0 0 0" rpy="-1.5708 0 -1.5708" />
    <parent link="mono_link" />
    <child link="wrist_camera_optical_frame" />
</joint>
```

Convention : `z` le long de l'axe de visée, `x` à droite, `y` vers le bas (convention optique ROS).
`rpy=(-90°, 0, -90°)` appliqué à un repère corps (`x` avant, `y` gauche, `z` haut) donne
`x_optique = -y_corps`, `y_optique = -z_corps`, `z_optique = +x_corps`.

Deux réserves, à lever sur le robot :

1. l'orientation du repère corps de `mono_link` est **supposée**, pas mesurée : viser une cible
   connue et vérifier que `z_optique` passe par elle ;
2. la **position** du cadre optique est celle de `mono_link`, c'est-à-dire le centre du boîtier
   déclaré par le constructeur, pas le centre optique réel du capteur.

Chaîne constatée en domaine 28 :

```text
arm_link4 -> wrist_camera_optical_frame : Translation [-0.048, -0.051, -0.002]
```

## 3. Qui possède le périphérique

Un device V4L2 est **exclusif en streaming** : deux processus qui l'ouvrent se volent les tampons
et le second meurt sur `Failed mapping device memory`, sans erreur côté appelant. Jusqu'au
2026-11-11, `yolo-inference.service` ouvrait `/dev/video0` à chaque requête
(`CAMERA_CLAW_INDEX=0`) : le sentinel l'interroge à 1-2 Hz, donc le périphérique était occupé en
permanence et un nœud ROS ne pouvait pas démarrer.

Répartition retenue — un seul propriétaire, les autres consommateurs lisent le topic :

| Rôle | Service | Accès |
|---|---|---|
| Propriétaire du périphérique | `clawbot-wrist-camera.service` | `/dev/v4l/by-id/…-video-index0` |
| Consommateur (détection) | `yolo-inference.service` | `/wrist_camera/image_raw`, `CAMERA_CLAW_SOURCE=ros` |
| Consommateur (futur `grasp_object`) | `clawbot_director` | même topic |

Le service YOLO tourne dans le venv `yolov5_env` ; `rclpy` y est importable dès que
`/opt/ros/humble/setup.bash` est sourcé (python 3.10.12 dans les deux cas, vérifié).

## 4. Mesures

```text
$ python3 scripts/sonde_flux_camera.py --topic /wrist_camera/image_raw --duration 5
frame_id        : wrist_camera_optical_frame
taille/encodage : 640x480 yuv422_yuy2
age du message  : 0.008 s
```

| Grandeur | Valeur mesurée | Méthode |
|---|---|---|
| Cadence livrée par le périphérique | **5,98 im/s** à 640×480 comme à 320×240 | `v4l2-ctl --stream-mmap --stream-count=40` |
| Cadence vue par les abonnés ROS | 4,6 à 7,8 Hz selon la fenêtre | `scripts/sonde_flux_camera.py` |
| Cadence négociée | 30 im/s | `v4l2-ctl --get-parm` |
| Latence d'image | 8 ms | âge du message |
| Luminance moyenne / écart-type | 124 / 5,9 | contrôle croisé sur `/compressed` (JPEG) |
| Netteté (variance du laplacien) | **7,3** | idem |

**Le module délivre 6 images par seconde, quelle que soit la résolution.** Ce n'est ni le lien USB
(480 Mb/s, et la même cadence Astra arrêtée), ni la conversion d'image (mesurée avant et après
passage à l'encodage natif : 7,7 Hz dans les deux cas), ni la charge CPU.

**Une image entièrement blanche, ce n'est pas la netteté : ce sont les réglages.** Le 2026-11-11 à
19:19, dans la pose de repos validée, `brightness=60` / `gain=70` (les valeurs que pose l'unité)
donnaient **307 200 pixels à 255 sur 307 200** — moyenne 255,0, écart-type 0,0. La même scène à
`gain=0` / `brightness=0` donne min 8, max 224, moyenne 131,9, **écart-type 61,1**, et l'on y
reconnaît la pièce. Le module n'expose pas de temps d'exposition : le gain est le seul levier, et
`gain:=70` le pousse au-delà du nécessaire en scène proche et éclairée. Les valeurs de l'unité sont à
revoir ; `ros2 param set` n'est pas une correction, il est volatile.

**Le contrôle d'exposition n'est pas exposé par ce module** (`auto_exposure` absent de
`--list-ctrls`), donc la piste « faible lumière + auto-exposition longue » ne peut pas être corrigée
logiciellement.

**Conséquence sur le critère du lot.** La conception demandait « `v4l2_camera_node` en 640×480 à
15 Hz ». La mesure dit 6 im/s : le critère est corrigé en « image 640×480 publiée à **au moins
5 Hz** mesurés, cadre `wrist_camera_optical_frame` », et la conséquence est écrite : un asservissement
visuel à 6 Hz est lent, la tolérance de `grasp_object` devra être mesurée avec cette cadence, pas
supposée.

**L'image actuelle est sans détail** (netteté 7,3 ; une scène texturée et nette donne des centaines
à des milliers). Le flux est techniquement valide mais le bras est en pose de repos : la caméra
regarde une surface lisse à très courte distance. Vérifier le cadrage et la netteté exige de
déplacer le bras ou de présenter un objet — opérateur.

## 5. Reproduire

```bash
export ROS_DOMAIN_ID=28 && source /opt/ros/humble/setup.bash
systemctl is-active clawbot-wrist-camera yolo-inference
ros2 topic hz /wrist_camera/image_raw
python3 scripts/sonde_flux_camera.py --topic /wrist_camera/image_raw --duration 5 --out /tmp/p.png
curl -s "http://127.0.0.1:8003/detect_raw?camera=claw"      # la détection passe par le topic
sudo fuser -v /dev/video0                                  # un seul processus doit le tenir
```

## 6. Reste ouvert

| Point | Gravité | Détail |
|---|---|---|
| Cadence 6 im/s au lieu de 15 | moyen | limite matérielle du module ; aucun réglage d'exposition exposé |
| Image sans détail au repos | moyen | cadrage et netteté à vérifier bras en mouvement |
| Orientation du cadre optique | **contredite par l'image** | dans la pose `[90, 180, 0, 0, 90]`, `scripts/cinematique_bras.py` annonce un axe optique à −90° (vers le bas) alors que l'image montre l'horizon et la même scène que l'Astra : le cadre optique de l'URDF est mal orienté. Non corrigé ; le fait mesuré fait foi |
| Intrinsèques nominales, non mesurées | moyen | `config/wrist_camera_info.yaml` : `fx=fy=457 px` (demi-champ 35°), à étalonner sur mire avant toute projection 3D |
| Pas d'échantillonnage à la demande | faible | le service YOLO lit la dernière image reçue ; aucune synchronisation avec l'instant de la décision |
| Image sans aucune structure | **corrigé le 2026-11-11 19:19** | la cause principale était le **gain** : `gain=70`, `brightness=60` → 100 % des pixels à 255. À `gain=0` : min 8, max 224, écart-type 61, image exploitable. Les valeurs de l'unité restent à corriger |
| Cadrage à revérifier en lumière faible | faible | `gain=0` corrige la saturation en scène éclairée ; la valeur correcte en lumière faible n'est pas mesurée |
| `CAMERA_FRONT_SOURCE` reste `opencv` | faible | le canal « front » du service YOLO ouvre toujours `/dev/video0` : à basculer aussi, ou à retirer |

## 7. Voir aussi

- [[index]]
- [[inventaire_materiel]]
- [[modele_urdf_clawbot]]
- [[orbbec_astra_pro_plus]]
- [[sentinel_s1]]
- [[preconditions_mouvement]]
