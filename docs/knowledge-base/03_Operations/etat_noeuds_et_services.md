---
title: "État des nœuds ROS 2 et des services systemd"
date: "2026-11-10T13:27:41+08:00"
author: "Hermes Agent"
tags: [operations, etat, ros2, systemd, services, noeuds]
status: actif
generated: true
---

# État des nœuds ROS 2 et des services systemd

Instantané relevé le 2026-11-10T13:27:41+08:00 sur le poste, domaine ROS 2 `28`. Cette page est un relevé, pas un engagement : elle est régénérée par `scripts/generate_status.py` et ne se modifie pas à la main.

## 1. Services systemd

| Unité | Rôle | État | Actif depuis |
|---|---|---|---|
| `ros2-driver-node.service` | Nœud de conduite (cmd_vel → série) | active (running) | Mon 2026-11-09 18:20:54 CST |
| `ros2-hardware-service.service` | Service matériel du pont C++ | active (running) | Mon 2026-11-09 18:20:54 CST |
| `ros2-llm-bridge-cpp.service` | Pont LLM historique (port 8000) | active (running) | Tue 2026-11-10 06:33:33 CST |
| `orbbec-camera.service` | Caméra Orbbec Astra Pro+ | active (running) | Mon 2026-11-09 18:20:54 CST |
| `rosbridge.service` | Passerelle WebSocket (port 9090) | active (running) | Mon 2026-11-09 18:20:54 CST |
| `yolo-inference.service` | Inférence YOLO (port 8003) | active (running) | Mon 2026-11-09 18:20:54 CST |
| `clawbot-joy-teleop.service` | Téléopération manette | active (running) | Tue 2026-11-10 13:25:47 CST |
| `clawbot-health.service` | Test de santé des périphériques | inactive (dead) | n/a |
| `clawbot-docs.service` | Site de documentation (port 8080) | active (running) | Tue 2026-11-10 13:26:37 CST |

## 2. Graphe ROS 2

Nœuds visibles : **7** — topics : **26**.

| Nœud |
|---|
| `/camera/camera` |
| `/driver_node` |
| `/hardware_service_node` |
| `/llm_bridge_node` |
| `/rosapi` |
| `/rosapi_params` |
| `/rosbridge_websocket` |

## 3. Santé des périphériques

Verdict **failed** en 7190 ms ([[llm2ros_health_test_specification]]).

| Périphérique | Requis | Verdict | Détail |
|---|---|---|---|
| `PER-01` camera couleur | oui | ok | — |
| `PER-02` camera profondeur | oui | ok | — |
| `PER-03` centrale inertielle | oui | ok | — |
| `PER-04` carte de commande | oui | ok | — |
| `PER-05` batterie | oui | ok | — |
| `PER-06` lidar | non | unavailable | périphérique déclaré non installé sur ce robot — HLT-E-NOT-INSTALLED |
| `PER-07` manette | non | failed | aucune manette presente sur le bus d'entree — HLT-E-DEVICE-ABSENT |
| `PER-08` chaine de detection | non | ok | — |
| `PER-09` arbre TF | oui | failed | cadres absents : base_link, odom, map — HLT-E-NODE-ABSENT |

## 4. Ressources du poste

| Mesure | Valeur |
|---|---|
| Charge (1 / 5 / 15 min) | 2.23 / 1.81 / 1.55 |
| Mémoire disponible | 10251 Mo sur 15655 Mo |
| Disque libre | 12.4 Go |
| Températures | cpu-thermal 53 °C, gpu-thermal 50 °C, cv0-thermal 49 °C, cv1-thermal 48 °C, cv2-thermal 45 °C, soc0-thermal 48 °C, soc1-thermal 47 °C, soc2-thermal 46 °C, tj-thermal 53 °C |
| Disponibilité du poste | 8 h 33 min |

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
