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

Le robot est sur cales, **roues en l'air** : il ne peut pas translater, seules les roues tournent. Toute consigne de vitesse non nulle produit une rotation de roues à **vitesse saturée** (~0,82 m/s), **indépendante de la consigne**, et de **signe opposé** à celle-ci :

| Consigne `linear.x` | `/vel_raw.linear.x` en régime (moyenne) | Min / max sur la fenêtre |
|---|---|---|
| `+0,05 m/s` | **−0,680 m/s** | −1,276 / 0,000 |
| `+0,10 m/s` | **−0,836 m/s** | −1,295 / 0,000 |
| `+0,20 m/s` | **−0,816 m/s** | −1,303 / 0,000 |
| `−0,10 m/s` | **+0,813 m/s** | −0,003 / +1,253 |

Trois consignes de 0,05 à 0,20 m/s donnent la même vitesse à 3 % près : ce n'est pas une erreur d'échelle, c'est une **saturation de la boucle de vitesse**. Le signe opposé et la saturation pour toute consigne non nulle sont la signature d'une contre-réaction de signe inversé (signe moteur ou signe encodeur), l'erreur `consigne − mesure` augmentant au lieu de diminuer jusqu'à la butée.

Chaîne concernée : `geometry_msgs/Twist` → `Mcnamu_driver_X3.py` (`cmd_vel_callback`, aucune correction) → `Rosmaster_Lib.set_car_motion()` (valeurs en mm/s) → PID du MCU (firmware 3.5, `kp 0,8 / ki 0,06 / kd 0,5`) → encodeurs.

## 2. Preuves

Relevé par paliers de 3 s, moyenne sur la seconde moitié de chaque palier (20 à 24 échantillons) :

```
odom initial (0.0, 0.0)
consigne +0.05 m/s -> vel_raw regime moyen -0.680 m/s (min -1.276 max +0.000, 20 ech.)
   odom apres: (-2.491, 0.047)
consigne +0.10 m/s -> vel_raw regime moyen -0.836 m/s (min -1.295 max +0.000, 24 ech.)
   odom apres: (-5.558, 0.139)
consigne +0.20 m/s -> vel_raw regime moyen -0.816 m/s (min -1.303 max +0.000, 24 ech.)
   odom apres: (-8.987, 0.212)
consigne -0.10 m/s -> vel_raw regime moyen +0.813 m/s (min -0.003 max +1.253, 24 ech.)
   odom apres: (-6.222, 0.243)
```

Les positions `odom` sont l'intégration de ces vitesses : le robot étant sur cales, elles mesurent la **rotation des roues**, pas une translation.

Mesure directe roue par roue, service arrêté, bibliothèque `Rosmaster_Lib` :

```
encodeurs au repos           (-45442, -45323, -38840, -45689)
encodeurs apres PWM +30 1,5s (-48231, -48207, -41225, -48009)
delta par roue               (-2789, -2884, -2385, -2320)

motion avant cmd             (0.0, 0.0, 0.0)
motion pendant cmd +0,10     (-1.287, 0.011, 0.493)
motion apres arret           (0.0, 0.0, 0.0)
delta encodeurs pendant cmd  (-9337, -9530, -7702, -8361)
```

Les quatre encodeurs avancent du même signe négatif, y compris en commande ouverte : le défaut est **global** (convention de signe du firmware ou du type de châssis), il ne vient pas d'un seul moteur câblé à l'envers. La vitesse angulaire `0,493 rad/s` apparaît alors que `angular.z = 0`.

Essai antérieur de 2 s à 0,12 m/s via `/cmd_vel`, même chaîne :

```
debut      : odom=(+0.000, +0.000)  degagement frontal=3.97 m
marche avant 0,12 m/s pendant 2,0 s
apres avant: odom=(-1.658, +0.051)  deplacement=1.659 m  degagement=3.97 m
marche arriere -0,10 m/s pendant 2,0 s
apres retour: odom=(-0.051, +0.003)  deplacement=1.608 m
```

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
