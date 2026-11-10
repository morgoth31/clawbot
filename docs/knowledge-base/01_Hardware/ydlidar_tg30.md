---
title: "YDLIDAR TG30 — télémètre laser 360° du châssis"
date: "2026-11-10T11:21:26+01:00"
author: "Hermes Agent"
tags: [hardware, lidar, ydlidar, tg30, tof, scan, ros2, cp2102]
status: validé
---

# YDLIDAR TG30 — télémètre laser 360°

Source de perception planaire du Clawbot X3, montée à l'avant du châssis et publiant `/scan`. Retour à l'[[index]] ; consommation par la navigation : [[ros2_nav_stack]] ; documentation constructeur : [[documentation_constructeur_yahboom]].

## 1. Identification

| Élément | Valeur | Source |
|---|---|---|
| Modèle annoncé par le pilote | `TG30` | `journalctl -u clawbot-lidar.service` — `Model: TG30` |
| Version de firmware | `1.71` | idem — `Firmware version: 1.71` |
| Version matérielle | `1` | idem — `Hardware version: 1` |
| Numéro de série | `2025041700100211` | idem — `Serial: 2025041700100211` |
| Version du SDK YDLIDAR | `1.0.6` | idem — `[YDLIDAR]:SDK Version: 1.0.6` |
| Bride USB-série | `Silicon Labs CP2102`, `10c4:ea60`, série `0001`, pilote `cp210x` | `udevadm info -q property -n /dev/ttyUSB0` |
| Nom stable udev | `/dev/ydlidar` → `ttyUSB0` | `ls -l /dev/ydlidar` |
| Débit série | `512 000 Bd` | `ros2 param get /ydlidar_ros2_driver_node baudrate` |

Horodatage de capture : 2026-11-10 11:16 CET pour `udevadm` et les paramètres ; 2026-11-10 08:10:09 CET pour la trace de démarrage du pilote, `ROS_DOMAIN_ID=28`.

Le lidar n'est donc pas sur le pont CH340 de la carte de commande mais sur le second pont CP2102 : la ligne « aucun nœud ROS 2 ne l'ouvre » de [[rosmaster_x3_mcu]] est corrigée par cette page.

## 2. Principe de mesure

Le TG30 est un télémètre laser **TOF** (temps de vol) à balayage mécanique 360°, et non un triangulateur : le constructeur classe le TG dans la famille TOF (`lidar_type: 0`, `TYPE_TOF`) et décrit le procédé dans `12.Lidar course/1.Lidar basics-EAI/1.Lidar basics.pdf` (dépôt `YahboomTechnology/ROSMASTERX3-PLUS`). Le firmware compense un décalage angulaire de `-4,75°` lu dans le lidar (`Successfully obtained the corrected offset angle[-4.750000]`), ce que reflète `angle_increment` ci-dessous.

## 3. Paramètres actifs

Relevés par `ros2 param get /ydlidar_ros2_driver_node <nom>` et confirmés par le fichier de configuration `/home/jetson/clawbot/config/ydlidar_x3plus.yaml` :

| Paramètre | Valeur | Remarque |
|---|---|---|
| `port` | `/dev/ydlidar` | lien udev, jamais `ttyUSB0` en dur |
| `frame_id` | `laser_link` | aligné sur l'URDF, cf. §6 |
| `baudrate` | `512000` | — |
| `lidar_type` | `0` | `TYPE_TOF` |
| `device_type` | `0` | série (1 = TCP) |
| `sample_rate` | `20` | 20 kHz, taille fixe 2 020 points/tour |
| `frequency` | `10.0` | consigne de rotation |
| `angle_min` / `angle_max` | `-180.0` / `180.0` | tour complet, degrés |
| `range_min` / `range_max` | `0.01` / `50.0` | mètres |
| `fixed_resolution` | `true` | pas angulaire constant |
| `reversion` / `inverted` | `true` / `true` | sens de rotation et orientation |
| `auto_reconnect` | `true` | reprise après coupure série |
| `isSingleChannel` / `intensity` | `false` / `false` | pas de canaux ni d'intensité |
| `support_motor_dtr` | `false` | moteur non piloté par DTR |
| `invalid_range_is_inf` | `false` | valeurs invalides remises à zéro |
| `abnormal_check_count` | `4` | — |

## 4. Signal publié

Capture `ros2 topic echo --full-length /scan --once`, 2026-11-10 11:23 CET, domaine 28 :

| Champ | Valeur |
|---|---|
| Type | `sensor_msgs/msg/LaserScan` |
| `frame_id` | `laser_link` |
| Nombre de points | 2 020 |
| `angle_min` / `angle_max` | `-3,1415927` / `+3,1415927` rad (±180°) |
| `angle_increment` | `0,0031120` rad (0,1783°) |
| `range_min` / `range_max` | `0,01` / `50,0` m |
| `scan_time` | `0,099394` s |
| `time_increment` | `50,0 µs` |
| Distances observées sur la capture | 0,000 m à 7,694 m, aucune valeur `inf` ni `NaN` |
| Cadence mesurée | `10,05 Hz` (12 messages, min 0,096 s, max 0,101 s, écart-type 0,0019 s) |

Sources : `ros2 topic echo --full-length /scan --once` et `ros2 topic hz /scan`.

### QoS : abonné en RELIABLE = aucun message

Le nœud publie `/scan` en `BEST_EFFORT` / `VOLATILE` (`ros2 topic info -v /scan`). Tout abonné qui demande `RELIABLE` est rejeté par le middleware et le pilote le journalise à chaque tentative :

```
[WARN] [ydlidar_ros2_driver_node]: New subscription discovered on topic '/scan',
requesting incompatible QoS. No messages will be sent to it.
Last incompatible policy: RELIABILITY_QOS_POLICY
```

Quatre occurrences enregistrées le 2026-11-10 (08:11, 08:23, 08:26, 09:22). Un affichage vide dans RViz 2 ou un nœud de navigation muet doit donc faire vérifier la QoS de l'abonné avant de suspecter le lidar.

## 5. Chaîne logicielle et exploitation

| Élément | Valeur | Source |
|---|---|---|
| Paquet | `ydlidar_ros2_driver` | `~/yahboomcar_ros2_ws/software/library_ws/src/ydlidar_ros2_driver` |
| Lanceur | `ydlidar_raw_launch.py`, `params_file:=/home/jetson/clawbot/config/ydlidar_x3plus.yaml` | `systemctl cat clawbot-lidar.service` |
| Unité systemd | `clawbot-lidar.service` (`Restart=on-failure`, `RestartSec=5`) | idem |
| Domaine | `ROS_DOMAIN_ID=28` | idem |
| Cadence de démarrage | connexion en 758 ms, scan actif en 1 063 ms après lancement | `journalctl -u clawbot-lidar.service` |

```bash
sudo systemctl restart clawbot-lidar.service
systemctl is-active clawbot-lidar.service
export ROS_DOMAIN_ID=28 && source /opt/ros/humble/setup.bash
ros2 topic hz /scan          # ~10 Hz
ros2 topic echo --once --field ranges /scan | head -3
```

## 6. Rattachement TF

`/tf_static` contient `base_link` → `laser_link` avec translation `(x = 0,105 m, y = 0,000 m, z = 0,047 m)` et rotation nulle (`ros2 run tf2_ros tf2_echo base_link laser_link`, 2026-11-10 11:22 CET). Le cadre `odom` et `map` restent absents : [[ERR-2026-11-10-003_arbre_tf_incomplet]] demeure ouverte pour cette raison, alors que le cadre de base existe désormais.

## 7. Écart avec la référence constructeur

Le dépôt constructeur fournit `TG.launch` (ROS 1, `software/library_ws/src/ydlidar_ros_driver-master/launch/TG.launch`) avec `port=/dev/ydlidar`, `baudrate=512000`, `lidar_type=0`, `sample_rate=20`, `range_max=50.0`, `frequency=10.0` — identiques à notre configuration. Une seule différence : `angle_min=-90` / `angle_max=90` chez le constructeur, contre ±180 ici, donc un tour complet au lieu d'un demi-tour. Le reste du fichier constructeur est repris tel quel, ce qui confirme que la configuration embarquée est bien celle du TG et non celle d'un X2/X3 (triangulation, 8 000 Bd).

## 8. Limites constatées

- Aucune procédure d'étalonnage de distance n'est documentée ni exécutée : seule la compensation d'offset angulaire constructeur (`-4,75°`) est appliquée.
- `intensity: false` : aucune intensité de retour publiée, donc pas de discrimination matière/réflectivité.
- Pas de page de mesure de précision (répétabilité, dérive thermique) : `Donnée non disponible — aucune campagne métrologique`.
- `range_max` configuré à 50 m alors que le `README.md` constructeur annonce une portée de 30 m pour le lidar 4ROS/TOF du X3 PLUS : les distances au-delà de 30 m ne sont garanties par aucune source.

## 9. Voir aussi

- Carte de commande et ponts série : [[rosmaster_x3_mcu]]
- Chaîne de navigation consommatrice : [[ros2_nav_stack]]
- Graphe ROS 2 complet : [[ros2_graph_clawbot]]
- Unité systemd et redémarrages : [[systemd_robot_services]]
- Documentation constructeur et cours lidar d'origine : [[documentation_constructeur_yahboom]]
- Anomalie historique de l'absence de `/scan` : [[ERR-2026-11-10-001_absence_topic_scan]]
