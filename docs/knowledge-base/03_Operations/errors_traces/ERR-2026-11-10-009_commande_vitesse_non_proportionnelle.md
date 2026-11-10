---
title: "ERR-2026-11-10-009 — commande de vitesse non proportionnelle et signe inversé"
date: "2026-11-10T13:08:00+01:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, cmd_vel, vel_raw, odometrie, securite, navigation]
status: ouvert
---

# ERR-2026-11-10-009 — commande de vitesse non proportionnelle et signe inversé

| Champ | Valeur |
|---|---|
| Identifiant | `ERR-2026-11-10-009` |
| Horodatage de détection | 2026-11-10T12:38:00+01:00 (CET) |
| Domaine ROS 2 | 28 |
| Topics concernés | `/cmd_vel`, `/vel_raw`, `/odom` (calculée) |
| Composant lié | [[yahboomcar_bringup_driver_node]], [[rosmaster_x3_mcu]] |
| Gravité d'exploitation | **Bloquante pour la navigation** : toute consigne de vitesse produit un déplacement non proportionnel |
| Statut | ouvert |
| Mitigation appliquée | Aucune sur le robot ; les essais de cartographie sont arrêtés, le robot est laissé à l'arrêt (`/cmd_vel` à zéro, `/vel_raw` nul) |

## 1. Nature de l'échec

Une consigne `geometry_msgs/Twist.linear.x = 0,10` produit, sur `/vel_raw`, une vitesse **de signe opposé** et d'amplitude **environ dix fois supérieure** : `−1,079 m/s` au pic. La bibliothèque `Rosmaster_Lib.set_car_motion()` transmet la valeur en mm/s (`int(v_x*1000)`), sans facteur d'échelle, et le nœud de conduite transmet `msg.linear.x` sans correction (`Mcnamu_driver_X3.py`, `cmd_vel_callback`).

## 2. Preuves

Relevé direct, consigne maintenue 1,5 s, 24 échantillons de `/vel_raw` :

```
consigne 0.10 m/s -> vel_raw x moyen -0.177 m/s (min -1.079 max 0.000, 24 echantillons)
echantillons: [0.0, 0.0, 0.0, -0.011, -0.023, -0.034, -0.073, -0.15, -0.235, -0.394, -0.796, -1.079]
```

Essai de déplacement correspondant, consigne `0,12 m/s` pendant 2,0 s (0,24 m attendus), odométrie intégrée depuis `/vel_raw` :

```
debut      : odom=(+0.000, +0.000)  degagement frontal=3.97 m
marche avant 0,12 m/s pendant 2,0 s
apres avant: odom=(-1.658, +0.051)  deplacement=1.659 m  degagement=3.97 m
marche arriere -0,10 m/s pendant 2,0 s
apres retour: odom=(-0.051, +0.003)  deplacement=1.608 m
```

Le retour à 5 cm du point de départ indique que la vitesse rapportée reste cohérente avec elle-même sur les deux sens : l'erreur est un facteur d'échelle et un signe, pas un bruit.

Contexte : [[2026-11-10_tests_cartographie]].

## 3. Actions de mitigation

| Horodatage | Action | Résultat mesuré |
|---|---|---|
| 2026-11-10T12:38:00+01:00 | Constat pendant l'essai de cartographie ; arrêt des essais de déplacement | Robot à l'arrêt |
| 2026-11-10T12:42:00+01:00 | `ros2 topic pub --once /cmd_vel` avec un Twist nul, SLAM et odométrie arrêtés | `/vel_raw` = `0,0` sur x, y et z |

Aucun réglage de firmware, de PID ni de paramètre n'a été tenté : corriger le facteur d'échelle sans comprendre son origine (unité du firmware 3.5, saturation PID, ou convention propre au châssis X3 PLUS) risquerait de masquer le défaut.

## 4. Conditions de clôture

1. Consigne `0,10 m/s` sur `/cmd_vel` : `/vel_raw.linear.x` compris entre `0,08` et `0,12 m/s` en régime établi, **de même signe** que la consigne.
2. Trois consignes (0,05 / 0,10 / 0,20 m/s) produisent trois vitesses mesurées proportionnelles, à ±20 %.
3. Déplacement mesuré au sol (mètre ruban sur 1,00 m) cohérent à ±5 cm avec l'odométrie.
4. Le sens physique du déplacement est vérifié pour une consigne positive **et** négative, roues levées puis au sol.

## 5. Voir aussi

- Essais de cartographie et mesures : [[2026-11-10_tests_cartographie]]
- Nœud de conduite : [[yahboomcar_bringup_driver_node]]
- Protocole série et firmware 3.5 : [[rosmaster_x3_mcu]]
- Chaîne de navigation à ne pas activer avant clôture : [[ros2_nav_stack]]
