---
title: "2026-11-10 — Mise en service de la manipulation : MoveIt 2 planifie et exécute jusqu'aux servos"
date: "2026-11-10T19:55:00+01:00"
author: "Hermes Agent"
tags: [operations, manipulation, moveit2, bras, servo, camera, systemd]
status: validé
---

# 2026-11-10 — Mise en service de la manipulation

Priorité 1 de l'état des lieux : donner au bras un chemin complet de la planification à
l'actionneur, et rendre utilisable la caméra du bras rebranchée le même jour.
Retour à l'[[index]] ; description technique : [[manipulation_moveit]].

## 1. Ce qui a été construit

| Livrable | Chemin | Nature |
|---|---|---|
| Serveur d'action de trajectoire | `~/clawbot/clawbot_arm_controller` (ament_python 0.1.0) | nouveau, versionné |
| Configuration MoveIt 2 | `~/clawbot/clawbot_moveit_config` (ament_cmake 0.1.0) | nouveau, versionné |
| Générateur de SRDF | `clawbot_moveit_config/scripts/generate_srdf.py` | nouveau |
| Outils de vérification | `clawbot_moveit_config/tools/plan_demo.py`, `tools/execute_demo.py` | nouveaux |
| Unité du contrôleur | `services/clawbot-arm-controller.service` | actif, activé au démarrage |
| Unité MoveIt | `services/clawbot-move-group.service` | démarrée à la demande |
| Fusion des états | `launch/robot_description.launch.py` (`source_list`) | modifié |
| Index caméra « claw » | `services/yolo-inference.service`, `services/ros2-hardware-service.service` (2 → 0) | modifié |

## 2. Chronologie des mesures

| Heure (CET) | Action | Résultat mesuré |
|---|---|---|
| 19:44 | `colcon build --packages-select clawbot_arm_controller clawbot_moveit_config` | 2 paquets compilés, 0 erreur |
| 19:45 | `pytest test` (domaine 99) | 18 tests purs verts, 4 tests d'action en échec (`goal_callback`) |
| 19:46 | correction de la signature du `goal_callback` | 4/4 tests d'action verts, 22/22 au total |
| 19:47 | premier lancement de `move_group` (domaine 28) | plan renvoyé : 101 points, **durée 0,00 s** |
| 19:48 | ajout de `request_adapters` dans `ompl_planning.yaml` | plan : 28 points, **2,61 s**, OMPL au lieu de CHOMP |
| 19:49 | `GET /detect_raw?camera=claw` après passage de l'index à 0 | HTTP 200, inférence 279 ms |
| 19:50 | démarrage de `clawbot-arm-controller.service` | actions servies, `/arm/joint_states` à 20,005 Hz |
| 19:51 | redémarrage de `clawbot-description.service` puis publication de test | `/joint_states` reflète `arm_joint1=0,11`, `arm_joint2=0,22` |
| 19:52 | démarrage de `clawbot-move-group.service` puis planification | `error_code 1`, 30 points, 2,85 s, calcul 0,013 s |

Chaîne complète exécutée sur le domaine isolé 99 (aucun abonné à `/servo_ctrl`, donc aucun
mouvement) : `error_code 1`, 41 consignes servo, écart final 0,029 rad pour une tolérance de
0,05 rad.

## 3. Essais physiques (22:39-22:55 CET, opérateur présent)

Prérequis confirmés par l'opérateur avant la première consigne : 40 cm libres autour du bras,
interrupteur batterie à portée, pince vide.

| Heure | Essai | Résultat mesuré |
|---|---|---|
| 22:39 | photo de l'espace de travail (caméra Astra) | scène trop sombre pour juger un mouvement : vérification faite par relecture des angles |
| 22:41 | pose lue sur la carte | `[71, 156, 55, -5, 90, 149]`, firmware 3.5, 11,90 V |
| 22:43 | axe 1 en direct : 71 → 76 → 81 → 91° | 71 → 73 → 76 → **75** : bloqué par le support de la caméra Orbbec |
| 22:44 | axe 1 sens inverse : 66° | **66°** exactement |
| 22:45 | axe 2 : 150° puis pince : 139° | 151° et **139°** |
| 22:47 | MoveIt, plan seul, axe 1 −5° | 14 points, `error_code 1`, aucun mouvement |
| 22:48 | MoveIt, plan + exécution, axe 1 −5° | servo 1 : 66 → **61°**, autres axes inchangés |
| 22:49 | MoveIt, retour axe 1 +5° | servo 1 : 61 → **66°** |
| 22:50 | pince par le serveur d'action : 129° puis 139° | 129° puis **139°**, `SUCCEEDED` |
| 22:51 | axe 1 restauré à 71°, axe 2 à 156°, pince à 149° | pose initiale retrouvée (servo 3 à 55° au lieu de 54°) |
| 22:52 | servo 2 : 146° puis 137° puis 127° | **127°** — dégage le support caméra (demande de l'opérateur) |
| 22:54 | pose synchronisée dans la configuration, contrôleur redémarré | `/arm/joint_states` = `[-0,3316, +0,6458, -0,6109, 0, 0, -0,2652]` |

Incident : à 22:52:55, un script de lecture a ouvert le port série alors que le pilote tournait ; le
pilote a levé `device reports readiness to read but returned no data (multiple access on port?)` et
systemd l'a relancé. `/voltage` est revenu à 10,000 Hz et 11,90 V. Les deux scripts de lecture
refusent maintenant de s'exécuter si l'unité est active.

## 4. Preuves brutes

```text
$ ROS_DOMAIN_ID=99 python3 clawbot_moveit_config/tools/execute_demo.py ready
etat vise        : ready [0.0, 0.5, 0.5, 0.0, 0.0]
error_code MoveIt: 1 (1 = SUCCESS)
consignes servo  : 41
derniers angles  : servo1=88°, servo2=117°, servo3=120°
/arm/joint_states: 46 messages
derniere consigne: arm_joint1=-0.029, arm_joint2=+0.479, arm_joint3=+0.520, arm_joint4=+0.009, arm_joint5=-0.009
ecart max        : 0.0292 rad (tolerance 0,05)
```

```text
$ ROS_DOMAIN_ID=28 python3 clawbot_moveit_config/tools/plan_demo.py demo
etat vise      : demo [0.3, 0.2 ...] -> error_code 1, 30 points, duree 2.85 s, planification 0.013 s
```

```text
$ ROS_DOMAIN_ID=28 python3 -m pytest test -q   (paquet clawbot_arm_controller)
22 passed, 1 warning in 7.77s
```

## 5. Effets de bord traités

| Effet | Traitement | Vérification |
|---|---|---|
| `joint_state_publisher` publiait 0 pour le bras, en concurrence avec le contrôleur | `source_list: ['/arm/joint_states']` | valeurs de test retrouvées dans `/joint_states` |
| Deux unités systemd supplémentaires | `clawbot-arm-controller` activé ; `clawbot-move-group` non activé | `systemctl is-active` : 11 unités actives |
| `/capture?camera=claw` répondait 500 | index passé de 2 à 0 dans l'unité déployée **et** dans la copie du dépôt | 200 confirmé sur 8001 et 8003 |
| Dérive dépôt/unité déployée (`WORKSPACE_PATH`) | copie du dépôt alignée sur l'unité déployée | `diff -u` vide hors commentaires |

## 6. Ce qui n'a pas été fait, et pourquoi

| Point | Raison |
|---|---|
| Axes 3, 4 et 5 | seuls les axes 1, 2 et la pince ont été commandés ; l'axe 4 est passif (retour invalide) et les axes 3 et 5 n'ont pas été essayés |
| Étalonnage des zéros servo | exige une mesure mécanique par servo ; la conversion actuelle est une convention documentée, pas une calibration |
| Vue avant (`front`) servie depuis l'Astra | demande une modification des deux services et du schéma d'outils C++ ; laissé ouvert, écart signalé dans les unités |
| `ros2_control` | chemin long (plugin matériel, relais vers le service 8001) ; le chemin court fonctionne et est mesuré |

## 7. Conditions de clôture vérifiables

1. `ros2 action list | grep controller` liste `arm_controller` et `grip_controller`.
2. `ros2 topic hz /arm/joint_states` donne 20 Hz et `/joint_states` suit ces valeurs.
3. `python3 clawbot_moveit_config/tools/plan_demo.py demo` renvoie `error_code 1` avec une durée
   strictement positive.
4. `curl 'http://127.0.0.1:8003/detect_raw?camera=claw'` renvoie HTTP 200.
5. `cd clawbot_arm_controller && ROS_DOMAIN_ID=99 pytest test -q` : 22 tests verts.
6. `python3 scripts/validate_okf.py` : 0 erreur.

## 8. Voir aussi

- Description technique : [[manipulation_moveit]]
- Bras et servos : [[bras_6dof]]
- Caméra du bras : [[camera_usb_bras]]
- Caméra RGB-D du châssis : [[orbbec_astra_pro_plus]]
- Rebranchement du même jour : [[2026-11-10_rebranchement_camera_bras]]
- Unités et dépendances : [[systemd_robot_services]]
