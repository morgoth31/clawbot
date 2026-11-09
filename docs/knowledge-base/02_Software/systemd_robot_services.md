---
title: "Services systemd et conteneurs Docker du robot"
date: "2026-11-10T06:13:48+08:00"
author: "Hermes Agent"
tags: [software, systemd, docker, supervision, services, ports]
status: validé
---

# Services systemd et conteneurs Docker du robot

Supervision de la pile applicative. Retour à l'[[index]] ; graphe ROS 2 correspondant : [[ros2_graph_clawbot]].

## 1. Unités systemd actives

Capture : `systemctl list-units --type=service`, 2026-11-10 06:10 CST.

| Unité | Description déclarée | État | Port / interface |
|---|---|---|---|
| `ros2-hardware-service.service` | Clawbot Hardware Service (ROS2 bridge — no serial conflict) | active (running) | `HARDWARE_SERVICE_PORT=8001` |
| `ros2-driver-node.service` | Clawbot ROS2 Driver Node (Mcnamu_driver_X3 — cmd_vel → serial) | active (running) | série `115 200 Bd` |
| `orbbec-camera.service` | Clawbot Orbbec Astra Pro+ Camera (depth + RGB → ROS2 topics) | active (running) | USB |
| `rosbridge.service` | Clawbot ROS2 WebSocket Bridge (Foxglove / rosbridge port 9090) | active (running) | 9090 |
| `ros2-llm-bridge-cpp.service` | Clawbot C++ LLM Bridge (port 8000) | active (running) | 8000 |
| `yolo-inference.service` | Clawbot YOLO Inference Service (port 8003, CUDA) | active (running) | 8003 |
| `clawbot-joy-teleop.service` | Clawbot Joy Teleop (Pro Controller / manette Bluetooth) | active (running) | périphérique d'entrée |
| `yahboom_oled.service` | transbot_oled start service | active (running) | bus I²C |

Huit unités actives, aucune unité en échec dans le filtre `ros|robot|yahboom|charles|claw`.

## 2. Variables d'environnement de la chaîne matérielle

Extrait de `systemctl cat ros2-hardware-service.service` :

```
ROS_DOMAIN_ID=28
WORKSPACE_PATH=/home/jetson/clawbot/workspace
CAMERA_FRONT_INDEX=0
CAMERA_CLAW_INDEX=2
HARDWARE_SERVICE_PORT=8001
MAX_LINEAR_MS=0.06
MAX_ANGULAR_RS=0.25
MOTION_WATCHDOG_S=1.5
LIDAR_SAFETY_REQUIRED=false
```

| Paramètre | Valeur | Effet documenté |
|---|---|---|
| `MAX_LINEAR_MS` | 0,06 m/s | Plafond de vitesse linéaire de la passerelle |
| `MAX_ANGULAR_RS` | 0,25 rad/s | Plafond de vitesse angulaire de la passerelle |
| `MOTION_WATCHDOG_S` | 1,5 s | Arrêt de sécurité en cas d'absence de commande |
| `LIDAR_SAFETY_REQUIRED` | `false` | Aucune source laser exigée pour autoriser le mouvement ([[ERR-2026-11-10-001_absence_topic_scan]]) |
| `ROS_DOMAIN_ID` | 28 | Domaine imposé à toute la pile |

## 3. Ordre de dépendance

`ros2-driver-node.service` déclare `After=network.target ros2-hardware-service.service` et `Requires=ros2-hardware-service.service` : l'arrêt de la passerelle matérielle entraîne l'arrêt du nœud de conduite.

## 4. Conteneurs Docker actifs

Capture : `docker ps`, 2026-11-10 06:10 CST.

| Conteneur | Image | État |
|---|---|---|
| `searxng` | `searxng/searxng:latest` | Up About an hour |
| `charles_robot_suite-charles-dashboard-1` | `yahboomtechnology/ros-foxy-orbslam2:1.0.0` | Up About an hour |

| Constat | Valeur |
|---|---|
| Distribution ROS dans l'image du tableau de bord | Foxy (image `ros-foxy-orbslam2:1.0.0`) |
| Distribution ROS de l'hôte | Humble (`/opt/ros/humble`) |
| Point d'entrée du projet Compose | `/home/jetson/charles_robot_suite/docker-compose.yml` |
| Réseau du conteneur tableau de bord | `br-0ebcc2854aa2`, 172.18.0.1/16 ([[jetson_orin_nx]] §5) |

La cohabitation Foxy (conteneur) / Humble (hôte) est constatée ; aucune communication DDS entre les deux distributions n'est documentée à ce stade : Donnée non disponible — `ros2 node list` sur le domaine 28 ne montre aucun nœud d'origine conteneurisée.

## 5. Voir aussi

- Nœud de conduite et lien série : [[yahboomcar_bringup_driver_node]]
- Chaîne de navigation (non déployée) : [[ros2_nav_stack]]
- Journal de la session de capture : [[2026-11-10_bootstrap_knowledge_base]]
