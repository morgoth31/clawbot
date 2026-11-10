---
title: "Nomenclature logicielle (BOM) du robot"
date: "2026-11-10T06:50:44+01:00"
author: "Hermes Agent"
tags: [software, bom, inventaire, dependances, versions]
status: actif
generated: true
---

# Nomenclature logicielle (BOM)

Relevé le 2026-11-10T06:50:44+01:00 par `scripts/generate_bom.py`. Toute ligne absente du poste est écrite `absent` : une nomenclature qui ne liste que l'installé ne dit pas ce qui manque.

## 1. Socle système

| Composant | Version | Source |
|---|---|---|
| Système d'exploitation | Ubuntu 22.04.5 LTS | `/etc/os-release` |
| Noyau | 5.15.148-tegra | `uname -r` |
| Paquet NVIDIA L4T | R36 (release), REVISION: 4.7, GCID: 42132812, BOARD: generic, EABI: aarch64, DATE: Thu Sep 18 22:54:44 UTC 2025 | `/etc/nv_tegra_release` |
| Python | 3.10.12 | exécutable `/usr/bin/python3` |
| Node.js | 22.22.1 | paquet système |
| ROS 2 | Humble (425 paquets `ros-humble-*`) | apt, `/opt/ros/humble` |

## 2. Bibliothèques Python

| Composant | Paquet | Version | Rôle | Criticité |
|---|---|---|---|---|
| mcp | `mcp` | 2.3.0 | SDK Model Context Protocol : serveur et client du pont | vital |
| rclpy | `ros-humble-rclpy` | 3.3.20-1jammy.20260217.060229 (apt) | Client Python ROS 2 (fourni par apt, pas par pip) | vital |
| fastapi | `fastapi` | 0.129.0 | API HTTP du service matériel et de la chaîne YOLO | vital |
| uvicorn | `uvicorn` | 0.41.0 | Serveur ASGI des mêmes API | vital |
| opencv-python | `opencv-python-headless` | 4.13.0.92 | Traitement d'image, capture caméra | vital |
| numpy | `numpy` | 2.2.6 | Calcul numérique, images et tenseurs | vital |
| torch | `torch` | 2.10.0 | Inférence YOLO sur GPU | important |
| ultralytics | `ultralytics` | 8.3.65 | Chargeur de modèles YOLO | important |
| pyserial | `pyserial` | 3.5 | Liaison série vers la carte de commande | vital |
| PyYAML | `PyYAML` | 6.0.2 | Configuration et frontmatter OKF | important |
| requests | `requests` | 2.32.3 | Appels HTTP sortants | important |
| httpx | `httpx` | 0.27.2 | Client HTTP asynchrone des tests | outillage |
| pytest | `pytest` | 9.2.0 | Exécution des suites de tests | vital |
| pytest-asyncio | `pytest-asyncio` | 1.3.0 | Tests asynchrones | outillage |
| pytest-timeout | `pytest-timeout` | 2.4.0 | Bornage des tests | outillage |
| mkdocs-material | `mkdocs-material` | 9.7.3 | Thème du site de documentation | important |
| pymdown-extensions | `pymdown-extensions` | 10.21 | Extensions Markdown (mermaid, admonitions) | important |

## 3. Paquets ROS 2 utilisés par le robot

| Paquet | Version | Rôle |
|---|---|---|
| `ros-humble-desktop` | absent | Métapaquet de la distribution |
| `ros-humble-rosbridge-suite` | absent | Passerelle WebSocket `/rosbridge_websocket` |
| `ros-humble-image-transport` | 3.1.12-1jammy.20260219.023156 | Transport des images caméra |
| `ros-humble-cv-bridge` | 3.2.1-1jammy.20260217.103424 | Conversion images ↔ OpenCV |
| `ros-humble-tf2-ros` | 0.25.19-1jammy.20260219.023214 | Transformations entre cadres |
| `ros-humble-rosbag2` | 0.15.16-1jammy.20260217.232604 | Enregistrement et relecture de topics |
| `ros-humble-nav2-bringup` | 1.1.20-1jammy.20260219.124457 | Pile de navigation (installée, non déployée) |
| `ros-humble-diagnostic-aggregator` | absent | Agrégation de diagnostics |

## 4. Outils en ligne de commande

| Outil | Version | Usage |
|---|---|---|
| `git` | 2.34.1 | Versionnement des sources et de la documentation |
| `colcon` | installé | Construction des espaces de travail ROS 2 |
| `ros2` | 0.18.17 | Inspection du graphe et exécution des nœuds |
| `jq` | 1.6 | Lecture JSON dans les scripts d'exploitation |
| `dot` (graphviz) | 2.43.0 | Rendu de graphes hors Mermaid |
| `v4l2-ctl` | 1.22.1 | Contrôle des périphériques vidéo |
| `mkdocs` | 1.6.1 | Construction du site de documentation |
| `gh` | absent | Gestion des tickets et PR GitHub |
| `frama-c` | absent | Preuve formelle C (skills ACSL installés, non exécutables) |

## 5. Incidences des absences

| Absence | Incidence | Contournement en place |
|---|---|---|
| `gh` | pas de gestion de tickets GitHub en ligne de commande | suivi local dans `.scratch/<fonctionnalite>/issues/` |
| `frama-c`, `why3`, `z3`, `coqc` | les skills de méthodes formelles sont installés mais ne peuvent pas prouver | analyse manuelle ; installation d'opam à prévoir |
| `ros-humble-nav2-bringup` si absent | aucune navigation autonome possible | trajectoires directes par le nœud de conduite |

## 6. Regénérer cette page

```bash
cd /home/jetson/clawbot
PYTHONPATH=$PWD python3 scripts/generate_bom.py
```

## 7. Voir aussi

- [[jetson_orin_nx]] — plateforme matérielle et système
- [[systemd_robot_services]] — unités qui exécutent ces composants
- [[ros2_graph_clawbot]] — nœuds et topics produits
- [[etat_noeuds_et_services]] — état d'exécution au dernier relevé
