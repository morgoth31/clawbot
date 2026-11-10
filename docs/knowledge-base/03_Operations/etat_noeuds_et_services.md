---
title: "État des nœuds ROS 2 et des services systemd"
date: "2026-11-10T22:56:03+01:00"
author: "Hermes Agent"
tags: [operations, etat, ros2, systemd, services, noeuds]
status: actif
generated: true
---

# État des nœuds ROS 2 et des services systemd

Instantané relevé le 2026-11-10T22:56:03+01:00 sur le poste, domaine ROS 2 `28`. Cette page est un relevé, pas un engagement : elle est régénérée par `scripts/generate_status.py` et ne se modifie pas à la main.

## 1. Services systemd

| Unité | Rôle | État | Actif depuis |
|---|---|---|---|
| `clawbot-description.service` | Description du robot (/robot_description, TF) | active (running) | Tue 2026-11-10 19:50:43 CET |
| `ros2-driver-node.service` | Nœud de conduite (cmd_vel → série) | active (running) | Tue 2026-11-10 22:54:46 CET |
| `ros2-hardware-service.service` | Service matériel du pont C++ | active (running) | Tue 2026-11-10 19:49:25 CET |
| `ros2-llm-bridge-cpp.service` | Pont LLM historique (port 8000) | active (running) | Tue 2026-11-10 19:49:25 CET |
| `orbbec-camera.service` | Caméra Orbbec Astra Pro+ | active (running) | Mon 2026-11-09 11:20:54 CET |
| `clawbot-lidar.service` | Lidar YDLIDAR TG30 (/scan) | active (running) | Tue 2026-11-10 08:10:07 CET |
| `clawbot-arm-controller.service` | Contrôleur de trajectoire du bras (→ /servo_ctrl) | active (running) | Tue 2026-11-10 22:54:56 CET |
| `clawbot-move-group.service` | MoveIt 2 move_group (démarré à la demande) | inactive (dead) | n/a |
| `rosbridge.service` | Passerelle WebSocket (port 9090) | inactive (dead) | Tue 2026-11-10 19:55:27 CET |
| `yolo-inference.service` | Inférence YOLO (port 8003) | active (running) | Tue 2026-11-10 19:49:41 CET |
| `clawbot-joy-teleop.service` | Téléopération manette | active (running) | Tue 2026-11-10 22:53:59 CET |
| `clawbot-health.service` | Test de santé des périphériques | inactive (dead) | n/a |
| `clawbot-docs.service` | Site de documentation (port 8080) | active (running) | Tue 2026-11-10 19:52:56 CET |

## 2. Graphe ROS 2

Nœuds visibles : **11** — topics : **29**.

| Nœud |
|---|
| `/arm_trajectory_server` |
| `/camera/camera` |
| `/driver_node` |
| `/hardware_service_node` |
| `/joint_state_publisher` |
| `/launch_ros_1598014` |
| `/llm_bridge_node` |
| `/robot_state_publisher` |
| `/rviz` |
| `/transform_listener_impl_5a41ea2b6890` |
| `/ydlidar_ros2_driver_node` |

## 3. Santé des périphériques

Verdict **failed** en 7603 ms ([[llm2ros_health_test_specification]]).

| Périphérique | Requis | Verdict | Détail |
|---|---|---|---|
| `PER-01` camera couleur | oui | ok | — |
| `PER-02` camera profondeur | oui | ok | — |
| `PER-03` centrale inertielle | oui | ok | — |
| `PER-04` carte de commande | oui | ok | — |
| `PER-05` batterie | oui | ok | — |
| `PER-06` lidar | oui | ok | — |
| `PER-07` manette | non | failed | aucune manette presente sur le bus d'entree — HLT-E-DEVICE-ABSENT |
| `PER-08` chaine de detection | non | ok | — |
| `PER-09` arbre TF | oui | failed | cadres absents : base_link, odom, map — HLT-E-NODE-ABSENT |

## 4. Ressources du poste

| Mesure | Valeur |
|---|---|
| Charge (1 / 5 / 15 min) | 2.22 / 2.47 / 2.18 |
| Mémoire disponible | 9488 Mo sur 15655 Mo |
| Disque libre | 22.5 Go |
| Températures | cpu-thermal 55 °C, gpu-thermal 52 °C, cv0-thermal 50 °C, cv1-thermal 50 °C, cv2-thermal 47 °C, soc0-thermal 50 °C, soc1-thermal 49 °C, soc2-thermal 48 °C, tj-thermal 55 °C |
| Disponibilité du poste | 25 h 1 min |

## 5. Ce que cette page ne prouve pas

- Un service `active` ne garantit pas qu'un périphérique est présent : c'est le rôle du test de
  santé, qui l'a établi pour la manette ([[llm2ros_health_test_specification]]).
- Un nœud présent dans le graphe ne publie pas nécessairement à la bonne cadence : les mesures
  de cadence figurent dans le rapport de santé, section 3.
- Ces valeurs sont un instantané : elles ne remplacent pas une supervision continue.

## 6. Regénérer cette page

```bash
cd /home/jetson/clawbot
PYTHONPATH=$PWD python3 scripts/generate_status.py
```

## 7. Voir aussi

- [[systemd_robot_services]] — description des unités et de leurs dépendances
- [[ros2_graph_clawbot]] — graphe de référence et cadences nominales
- [[llm2ros_health_test_specification]] — ce qui est vérifié sur les périphériques
