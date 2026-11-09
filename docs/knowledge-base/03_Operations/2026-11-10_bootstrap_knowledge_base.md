---
title: "Journal d'opération — création de la base de connaissances et capture initiale"
date: "2026-11-10T06:14:09+08:00"
author: "Hermes Agent"
tags: [operations, journal, capture, diagnostic, ros2, jetson]
status: validé
---

# Journal d'opération — 2026-11-10 06:11–06:16 CST

Session de création de `/Robot_Knowledge_Base/` et de capture de l'état initial des sous-systèmes. Retour à l'[[index]].

## 1. Environnement d'exécution

| Élément | Valeur |
|---|---|
| Hôte | `yahboom` (Jetson Orin NX, L4T R36.4.7, Ubuntu 22.04.5) — [[jetson_orin_nx]] |
| Utilisateur | `jetson` (uid `1000`, groupes `sudo`, `docker`, `i2c`, `gpio`, `video`) |
| Middleware | ROS 2 Humble, `ROS_DOMAIN_ID=28` — [[ros2_graph_clawbot]] |
| Accès `/` en écriture | Non pour `jetson` ; création de `/Robot_Knowledge_Base` via `sudo` (mot de passe non requis), puis `chown -R jetson:jetson` |

## 2. Séquence exécutée

| Heure (CST) | Commande | Code retour | Résultat retenu |
|---|---|---|---|
| 06:09:19 | `tegrastats` (2 s) | 0 | RAM, charges CPU, températures, tensions — [[jetson_orin_nx]] §2-3 |
| 06:09:24 | lecture `thermal_zone*/temp` + `trip_point_*` | 0 | 9 zones, trip points 70 / 99 / 104,5 °C |
| 06:10:03 | `lsusb` | 0 | Orbbec `2bc5:060f`, CH340 `1a86:7523`, CP2102 `10c4:ea60`, Microdia `0c45:6340` |
| 06:10:12 | `systemctl list-units` (filtre robot) | 0 | 8 unités actives — [[systemd_robot_services]] |
| 06:10:20 | `docker ps` | 0 | 2 conteneurs actifs — [[systemd_robot_services]] §4 |
| 06:11:53 | `df -h /` | 0 | 4,3 Go libres, 97 % — [[ERR-2026-11-10-002_espace_disque_critique]] |
| 06:12:44 | `ros2 topic echo --once /voltage` | 0 | 11,900 V — [[batterie_principale]] |
| 06:12:52 | `ros2 topic hz /voltage` | 0 | 10,000 Hz |
| 06:13:20 | `ros2 topic echo --once /imu/data_raw` | 0 | accélération z = −9,852 m/s², `frame_id=imu_link` |
| 06:13:35 | `ros2 topic hz /camera/color/image_raw` | 0 | 20,109 Hz (640 × 480 `rgb8`) |
| 06:13:41 | `ros2 topic hz /camera/depth/image_raw` | 0 | 29,995 Hz (640 × 480 `16UC1`) |
| 06:14:10 | `ros2 topic info /cmd_vel` | 0 | 2 éditeurs, 1 abonné, aucun message en 12 s |
| 06:14:30 | `ros2 topic list -t` | 0 | 26 topics ; `/scan`, `/odom`, `/battery_state` absents |
| 06:14:48 | `tf2_echo base_link camera_link` | 1 | `Invalid frame ID "base_link"` — [[ERR-2026-11-10-003_arbre_tf_incomplet]] |

## 3. Fait déterminant relevé pendant la capture

Une première requête `ros2 node list` sans `ROS_DOMAIN_ID=28` retourne une liste vide (seuls `/rosout` et `/parameter_events` visibles). Toutes les unités systemd du robot imposent `ROS_DOMAIN_ID=28` :

```
ROS_DOMAIN_ID=28
```

Conséquence documentaire : toute commande ROS 2 destinée à ce robot doit inclure `export ROS_DOMAIN_ID=28` avant `source /opt/ros/humble/setup.bash`, sinon le graphe apparaît vide (`ros2 node list` → 0 nœud, `ros2 topic list` → 2 topics d'infrastructure).

## 4. Anomalies ouvertes à l'issue de la session

| Référence | Objet | Statut |
|---|---|---|
| [[ERR-2026-11-10-001_absence_topic_scan]] | Aucune source de scan laser publiée | ouvert |
| [[ERR-2026-11-10-002_espace_disque_critique]] | Partition racine à 97 % | ouvert |
| [[ERR-2026-11-10-003_arbre_tf_incomplet]] | TF sans `base_link`, sans `odom`, sans `map` | ouvert |

## 5. Documents créés

```
/Robot_Knowledge_Base/
├── index.md
├── 01_Hardware/jetson_orin_nx.md
├── 01_Hardware/rosmaster_x3_mcu.md
├── 01_Hardware/orbbec_astra_pro_plus.md
├── 01_Hardware/batterie_principale.md
├── 02_Software/ros2_graph_clawbot.md
├── 02_Software/yahboomcar_bringup_driver_node.md
├── 02_Software/systemd_robot_services.md
├── 02_Software/ros2_nav_stack.md
├── 03_Operations/2026-11-10_bootstrap_knowledge_base.md
└── 03_Operations/errors_traces/ERR-2026-11-10-00{1,2,3}_*.md
```

## 6. Voir aussi

- [[ros2_nav_stack]] — chaîne de navigation, non déployée à cette date
- [[yahboomcar_bringup_driver_node]] — nœud de conduite actif
