---
title: "Batterie principale — télémétrie de tension"
date: "2026-11-10T06:12:57+08:00"
author: "Hermes Agent"
tags: [hardware, energie, batterie, tension, telemetrie]
status: validé
---

# Batterie principale — télémétrie de tension

Chaîne d'alimentation du robot et mesure disponible. Retour à l'[[index]] ; acquisition via [[rosmaster_x3_mcu]].

## 1. Mesure disponible

| Grandeur | Valeur | Source | Horodatage |
|---|---|---|---|
| Tension pack | 11,900 V (`11.899999618530273`) | `/voltage` (`std_msgs/msg/Float32`) | 2026-11-10 06:12:44 CST |
| Cadence de publication | 10,000 Hz (période 100 ms, écart-type 0,19 ms) | `ros2 topic hz /voltage` | 2026-11-10 06:12:52 CST |

Origine de la mesure dans le nœud pilote : `battery.data = self.car.get_battery_voltage()*1.0`, publiée par `self.volPublisher` (`Mcnamu_driver_X3.py:62,143`), période 100 ms (`Mcnamu_driver_X3.py:69`).

## 2. Données non disponibles

| Grandeur | Statut | Code / preuve |
|---|---|---|
| État de charge (SoC, %) | Donnée non disponible | Aucune entrée sous `/sys/class/power_supply/` — répertoire vide (`ls /sys/class/power_supply/` sans sortie, code retour 0 avec liste vide) |
| Courant de décharge | Donnée non disponible | Aucun `current_now` dans `/sys/class/power_supply/` |
| Température batterie | Donnée non disponible | Aucun `temp` dans `/sys/class/power_supply/` |
| Seuil d'alerte basse tension | Donnée non disponible | Aucun seuil déclaré dans `yahboomcar_bringup` (recherche `voltage` : seules les lignes de publication) |
| Chimie et capacité nominale | Donnée non disponible | Aucune étiquette lisible par le système ; valeur non mesurée |

## 3. Conversion et exploitation

La chaîne logicielle n'expose que la tension brute ; toute décision de seuil repose sur une valeur externe. Seuil effectif utilisé par le robot : Donnée non disponible.

## 4. Voir aussi

- Lien série qui transporte la mesure : [[rosmaster_x3_mcu]]
- Consommation de la plateforme de calcul : [[jetson_orin_nx]]
- Graphe ROS 2 : [[ros2_graph_clawbot]]
