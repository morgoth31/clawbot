---
title: "Inventaire matériel du Clawbot X3 Plus — présence, fonction, nœud ROS 2"
date: "2026-11-11T00:15:00+01:00"
author: "Hermes Agent"
tags: [hardware, inventaire, ros2, verification, usb, capteurs]
status: validé
---

# Inventaire matériel — présence, fonction et nœud ROS 2

Relevé du 2026-11-11 entre 00:05 et 00:15 CET, `ROS_DOMAIN_ID=28`, robot alimenté
(`/voltage` 11,90 V). Chaque ligne porte sa mesure : un service `active` n'est jamais pris pour
une preuve de présence (règle de la base).

Retour à l'[[index]] ; graphe détaillé : [[ros2_graph_clawbot]] ; MCP : [[mcp_hermes]].

## 1. Tableau de synthèse

| # | Matériel | Identité mesurée | Présence | Fonction mesurée | Nœud ROS 2 | Verdict |
|---|---|---|---|---|---|---|
| 1 | Carte de commande Rosmaster | `1a86:7523`, `/dev/myserial` → `ttyUSB1`, firmware 3.5 | oui | `/voltage` 10,000 Hz (11,90 V), `/vel_raw` 9,999 Hz, `/imu/data_raw` 10,000 Hz, servos répondent | `driver_node` | **ok** |
| 2 | Lidar YDLIDAR TG30 | CP2102 `10c4:ea60`, `/dev/ydlidar` → `ttyUSB0` | oui | `/scan` 10,082 Hz, `frame_id: laser_link` | `ydlidar_ros2_driver_node` | **ok** |
| 3 | Caméra RGB-D Orbbec Astra Pro+ | `2bc5:060f` (profondeur) + `2bc5:050f` (couleur, `usbfs`) | oui | couleur 20,06 Hz, profondeur 29,99 Hz, IR 29,97 Hz, points 29,08 Hz | `/camera/camera` | **ok** |
| 4 | Caméra du bras (UVC) | `0c45:6340`, port `1-2.2.1`, `/dev/video0` + `video1` | oui | capture V4L2 et OpenCV, image vérifiée | **aucun** (accès OpenCV par les services 8001/8003) | présent, **hors graphe** |
| 5 | Bras 5 axes + pince | 6 servos bus, ids 1-6 via le MCU | oui | angles relus, 6 servos commandables (±1°), planification et exécution MoveIt validées | `arm_trajectory_server`, `move_group` | **ok** |
| 6 | IMU intégrée à la carte | via le MCU | oui | `/imu/data_raw` 10,000 Hz, `/imu/mag` publié | `driver_node` | ok (qualité non évaluée) |
| 7 | Batterie | aucune jauge, tension seule | oui | 11,90 V à 10 Hz | `driver_node` | **partiel** : pas d'état de charge |
| 8 | Roues + encodeurs | 4 moteurs via le MCU | oui | `/vel_raw` 9,999 Hz mais consigne non proportionnelle | `driver_node` | **dégradé** (ERR-009) |
| 9 | Buzzer et LED RGB | fonctions du MCU | oui (topics présents) | `/Buzzer`, `/RGBLight` existent ; **aucun essai d'action** | `driver_node` | présent, non testé |
| 10 | Manette de jeu | **aucun `/dev/input/js*`** | non | `clawbot-joy-teleop.service` actif sans périphérique | — | **service inutile** |
| 11 | Sortie audio (haut-parleur) | lecture : HDMI uniquement | **non** | `aplay -l` ne liste aucun haut-parleur USB/I2S | — | **absent** : le TTS n'a pas de sortie |
| 12 | Entrée audio (micro) | carte 0 (caméra USB), carte 1 (Astra) | oui | `arecord -l` liste deux entrées de capture | — | présent, **aucun nœud** |
| 13 | Odométrie `/odom` et TF `odom → base_link` | — | **non** | topic absent, transformation absente | aucun | **manquant** |
| 14 | Carte `/map` | — | non (hors session SLAM) | aucun message pendant 9 s | `slam_toolbox` non lancé | normal hors cartographie |

## 2. Ce que l'inventaire change dans le plan

| Constat | Conséquence |
|---|---|
| 9 périphériques sur 12 ont un nœud ROS 2 vivant et une mesure | la chaîne de base est saine ; les verrous sont logiciels (ERR-009, odométrie) et non matériels |
| La caméra du bras fonctionne mais n'a aucun nœud | elle n'est visible ni du graphe, ni de la supervision, ni de MoveIt ; seule la voie OpenCV la voit |
| Aucun haut-parleur détecté | la phase TTS du plan directeur est bloquée par le matériel, pas par le logiciel : prévoir un module audio USB |
| Pas de manette détectée alors que l'unité `joy-teleop` tourne | l'unité doit être arrêtée ou la manette branchée ; elle consomme sans servir |
| `/odom` et `odom → base_link` absents | Nav2 et `NavigateTo` resteront non fonctionnels même configurés (déjà tracé en ERR-003) |
| Buzzer et LED jamais sollicités | deux sorties d'alerte disponibles pour le superviseur S1, à tester avant de s'en servir |

## 3. Commandes de reproduction

```bash
export ROS_DOMAIN_ID=28; source /opt/ros/humble/setup.bash
lsusb; lsusb -t; ls -l /dev/serial/by-id/ /dev/v4l/by-id/
v4l2-ctl --list-devices; arecord -l; aplay -l; ls /dev/input/js* 2>/dev/null
ros2 node list; ros2 topic list -t
for t in /scan /voltage /vel_raw /imu/data_raw /camera/color/image_raw \
         /camera/depth/image_raw /camera/depth/points /camera/ir/image_raw; do
  printf '%-26s ' "$t"; ros2 topic hz "$t" 2>&1 | grep -m1 'average rate'
done
```

## 4. Voir aussi

- Graphe ROS 2 : [[ros2_graph_clawbot]]
- Carte de commande : [[rosmaster_x3_mcu]]
- Lidar : [[ydlidar_tg30]]
- Caméra RGB-D : [[orbbec_astra_pro_plus]]
- Caméra du bras : [[camera_usb_bras]]
- Bras et servos : [[bras_6dof]]
- Manipulation : [[manipulation_moveit]]
- Serveur MCP et accès depuis Hermes : [[mcp_hermes]]
- Anomalies de vitesse : [[ERR-2026-11-10-009_commande_vitesse_non_proportionnelle]]
