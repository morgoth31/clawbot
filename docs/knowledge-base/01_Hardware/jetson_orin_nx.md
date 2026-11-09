---
title: "Jetson Orin NX 16 Go — plateforme de calcul"
date: "2026-11-10T06:12:04+08:00"
author: "Hermes Agent"
tags: [hardware, jetson, orin-nx, tegrastats, thermique, l4t, stockage]
status: validé
---

# Jetson Orin NX 16 Go

Ordinateur embarqué du robot, hôte `yahboom`. Retour à l'[[index]].

## 1. Identification

| Propriété | Valeur | Source |
|---|---|---|
| Modèle | `NVIDIA Jetson Orin NX Engineering Reference Developer Kit` | `/proc/device-tree/model` |
| Noyau | `Linux yahboom 5.15.148-tegra #1 SMP PREEMPT Thu Sep 18 15:08:33 PDT 2025 aarch64` | `uname -a` |
| BSP | L4T R36.4.7 (GCID 42132812, build 2025-09-18) | `/etc/nv_tegra_release` |
| Distribution | Ubuntu 22.04.5 LTS | `/etc/os-release` |
| Cœurs CPU | 8 | `nproc` |
| Mode d'alimentation | `MAXN_SUPER` (id `0`) | `nvpmodel -q` |
| RAM totale | 15 656 Mo | `tegrastats` |
| Uptime à la capture | 1 h 17 min, 3 sessions | `uptime` |

## 2. Charge et consommation

Capture unique `tegrastats`, horodatage 2026-11-10 06:09:19 CST.

| Indicateur | Valeur |
|---|---|
| RAM utilisée | 5 805 / 15 656 Mo (lfb 1 × 4 Mo) |
| Swap | 0 / 16 020 Mo |
| Charge CPU (8 cœurs) | 8 % à 22 %, 729–1 984 MHz |
| Charge GPU (`GR3D_FREQ`) | 0 % |
| `VDD_IN` | 6 053 mW |
| `VDD_CPU_GPU_CV` | 1 134 mW |
| `VDD_SOC` | 1 608 mW |
| Load average (1/5/15 min) | 2,13 / 1,96 / 1,90 |

Sortie brute :

```
06:09:19 RAM 5805/15656MB (lfb 1x4MB) SWAP 0/16020MB (cached 0MB) CPU [22%@729,20%@1984,20%@1984,18%@1984,18%@729,12%@729,16%@729,8%@729] GR3D_FREQ 0% cv0@48.593C cpu@52.968C soc2@46.187C soc0@48.187C cv1@48.093C gpu@50.531C tj@52.968C soc1@47.218C cv2@44.875C VDD_IN 6053mW/6053mW VDD_CPU_GPU_CV 1134mW/1134mW VDD_SOC 1608mW/1608mW
```

## 3. Températures

Capture `tegrastats`, 2026-11-10 06:09:19 CST :

| Capteur | Température |
|---|---|
| cv0 | 48,59 °C |
| cv1 | 48,09 °C |
| cv2 | 44,88 °C |
| cpu | 52,97 °C |
| gpu | 50,53 °C |
| soc0 | 48,19 °C |
| soc1 | 47,22 °C |
| soc2 | 46,19 °C |
| tj | 52,97 °C |

Contrôle croisé sysfs, 2026-11-10 06:09:24 CST (`/sys/class/thermal/thermal_zone*/temp`, millidegrés) :

| Zone | Type | Température | Trip points (_0 / _1 / _2) |
|---|---|---|---|
| thermal_zone0 | cpu-thermal | 53,375 °C | 99 °C / 104,5 °C / 70 °C |
| thermal_zone1 | gpu-thermal | 50,531 °C | 99 °C / 104,5 °C / 70 °C |
| thermal_zone2 | cv0-thermal | 48,843 °C | 99 °C / 104,5 °C / 70 °C |
| thermal_zone3 | cv1-thermal | 48,156 °C | 99 °C / 104,5 °C / 70 °C |
| thermal_zone4 | cv2-thermal | 44,875 °C | 99 °C / 104,5 °C / 70 °C |
| thermal_zone5 | soc0-thermal | 48,062 °C | 99 °C / 104,5 °C / 70 °C |
| thermal_zone6 | soc1-thermal | 47,093 °C | 99 °C / 104,5 °C / 70 °C |
| thermal_zone7 | soc2-thermal | 46,062 °C | 99 °C / 104,5 °C / 70 °C |
| thermal_zone8 | tj-thermal | 53,437 °C | 99 °C / 104,5 °C / 70 °C |

Marge minimale à la capture : 16,6 °C sous le trip point passif de 70 °C (capteur cpu).

## 4. Stockage

| Point de montage | Périphérique | Taille | Utilisé | Libre | Occupation |
|---|---|---|---|---|---|
| `/` | `/dev/nvme0n1p1` | 147 Go | 136 Go | 4,3 Go | 97 % |

Occupation supérieure au seuil d'exploitation : anomalie ouverte [[ERR-2026-11-10-002_espace_disque_critique]].

## 5. Réseau

| Interface | État | Adresse | Rôle constaté |
|---|---|---|---|
| `wlP1p1s0` | UP | 192.168.1.47/24 + 3 adresses IPv6 globales | Liaison Wi-Fi principale |
| `lo` | UNKNOWN | 127.0.0.1/8, ::1/128 | Boucle locale |
| `can0` | DOWN | — | Bus CAN inactif |
| `docker0` | DOWN | 172.17.0.1/16 | Pont Docker par défaut |
| `br-0ebcc2854aa2` | UP | 172.18.0.1/16 | Pont du réseau Compose ([[systemd_robot_services]]) |
| `eno1` | DOWN | — | Ethernet filaire |
| `usb0`, `usb1` | DOWN | — | Gadget USB L4T |
| `l4tbr0` | DOWN | — | Pont gadget L4T |

## 6. Logiciels embarqués utiles

| Outil | Chemin / version |
|---|---|
| ROS 2 Humble | `/opt/ros/humble` |
| colcon | `/usr/bin/colcon` |
| Docker | `/usr/bin/docker` |
| Node.js | v22.22.1 |
| Python (interpréteur Hermes) | 3.14.9 |
| Python système | 3.10.12 |
| graphviz (`dot`) | 2.43.0 |
| `jq` | 1.6 |

## 7. Voir aussi

- Graphe ROS 2 actif : [[ros2_graph_clawbot]]
- Services supervisés : [[systemd_robot_services]]
