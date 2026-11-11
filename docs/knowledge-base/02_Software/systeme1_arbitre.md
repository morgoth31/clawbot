---
title: "Système 1 — proprioception du bras et arbitre réflexe"
date: "2026-11-11T13:00:00+01:00"
author: "Hermes Agent"
tags: [software, securite, arbitre, servo, proprioception, lot-2]
status: validé
---

# Système 1 — proprioception et arbitre réflexe (lot 2)

Retour à l'[[index]] ; conception : `docs/superpowers/specs/2026-11-11-architecture-s1-s2-design.md`.

## 1. Proprioception du bras

`/arm/servo_angles` (`std_msgs/Int32MultiArray`, 6 valeurs) est publié à ~10 Hz par le driver.
Une lecture de servo est bloquante (15-20 ms) : elle est **entrelacée**, un servo par tick
(`RoundRobin`), cycle complet en ~600 ms. Vérifié : `/imu` et `/vel_raw` restent à 10,000 Hz
pendant les lectures.

Premier relevé réel : `[76, 96, 90, 90, 90, 149]` — servo 2 à 96°, donc au-dessus du seuil de
95° : le réflexe anti-basculement appliquera `FREEZE` et non `DROP_TORQUE`.

## 2. Seuils (`clawbot_safety/thresholds.py`)

| Fonction | Règle |
|---|---|
| `tilt_state` | ≥ 8° → `hold` ; ≥ 12° et servo 2 < 95° → `drop_torque` ; ≥ 12° sinon → `freeze` ; angle invalide → `hold` |
| `obstacle_stop` | obstacle < 0,15 m **et** commande non nulle ; lidar muet → arrêt |
| `battery_state` | < 10,5 V pendant ≥ 2 s ; un pic plus court est ignoré (moyenne glissante 10 s) |
| `is_stale` | > 2 s sans message → alerte, jamais silence |

## 3. Arbitre (`clawbot_safety/arbitrator.py`, service `clawbot-safety-arbitrator`)

20 Hz, propriétaire de `/cmd_vel_safe`. Le driver n'écoute plus que ce topic : un seul écrivain.

| Vérification | Résultat |
|---|---|
| Cadence | tick 100 à 5 s → **20 Hz** |
| Consigne qui passe, monde dégagé | `/cmd_vel_safe` = 0,05 |
| Obstacle à 12 cm | mise à zéro en **47 ms** (critère < 100 ms), état `STOP` |
| Chien de garde de commande | sans `/cmd_vel` depuis 0,5 s, sortie à 0,0 |
| Basculement simulé | 9° → `HOLD` ; 13° avec servo 2 à 96° → `FREEZE` ; 13° avec servo 2 à 70° → `DROP_TORQUE` |
| Péremption | `/imu` absent → `SENSOR_STALE`, sortie à zéro |

## 4. Deux pièges qui ont coûté du temps

1. **Un service qui tourne en root est invisible du graphe.** L'arbitre tournait, publiait, mais
   aucun abonné ne recevait rien et `ros2 node list` ne le voyait pas : découverte DDS isolée entre
   root et `jetson`. Correctif : `User=jetson` dans l'unité. C'est aussi ce qui expliquait le
   `SENSOR_STALE` permanent, ses propres souscriptions ne recevant rien.
2. **La dernière consigne se perpétuait.** Sans `/cmd_vel` frais, l'arbitre republiait la dernière
   valeur à 20 Hz : le robot continuait d'avancer après l'arrêt de l'émetteur. Correctif :
   chien de garde de 0,5 s.

## 5. Chaîne complète : l'arbitre arrête le bras

`arm_trajectory_server` s'abonne à `/safety/hold` et interrompt la trajectoire en cours. Preuve de
bout en bout (`scripts/test_safety_hold.py`, domaine 99, contrôleur et arbitre réels avec IMU
simulée) :

```text
objectif accepte : True
inclinaison simulee a 13 deg -> l'arbitre doit publier hold
code : 0 | message : interrompu par safety hold apres 6 echantillons
SUCCES : trajectoire interrompue par le reflexe
```

### Le bug que ce test a révélé

Le contrôleur appelait `goal_handle.canceled()` pour s'arrêter. Or `canceled()` n'est valide
qu'après une **demande d'annulation du client** ; côté serveur, l'état attendu est `ABORTED`.
Résultat : `RCLError: attempted invalid transition from state EXECUTING with event CANCELED`, un
message « Goal state not set, assuming aborted », et **la trajectoire continuait**. Le garde-fou
semblait fonctionner dans les journaux tout en ne stoppant rien.

Correctif : `abort()` pour l'arrêt réflexe, `canceled()` conservé pour l'annulation cliente, avec
des messages distincts (`interrompu par safety hold` / `annule apres N echantillons`).

## 6. Ce qui reste ouvert

- Le test d'inclinaison réel : les seuils sont validés sur IMU simulée, pas sur la mesure physique.
- `DROP_TORQUE` est décidé et publié, mais **aucun étage ne coupe réellement le couple** des servos :
  le contrôleur s'arrête, la pince ne relâche pas. À traiter avec `set_uart_servo_torque`.
- Le temps mort de la base (~0,85 s) reste supérieur à ce qu'un asservissement visuel exige.
