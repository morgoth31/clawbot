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

## 3. Preuves brutes

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

## 4. Effets de bord traités

| Effet | Traitement | Vérification |
|---|---|---|
| `joint_state_publisher` publiait 0 pour le bras, en concurrence avec le contrôleur | `source_list: ['/arm/joint_states']` | valeurs de test retrouvées dans `/joint_states` |
| Deux unités systemd supplémentaires | `clawbot-arm-controller` activé ; `clawbot-move-group` non activé | `systemctl is-active` : 11 unités actives |
| `/capture?camera=claw` répondait 500 | index passé de 2 à 0 dans l'unité déployée **et** dans la copie du dépôt | 200 confirmé sur 8001 et 8003 |
| Dérive dépôt/unité déployée (`WORKSPACE_PATH`) | copie du dépôt alignée sur l'unité déployée | `diff -u` vide hors commentaires |

## 5. Ce qui n'a pas été fait, et pourquoi

| Point | Raison |
|---|---|
| Exécution réelle sur les servos | demande un opérateur, un dégagement mesuré autour du bras et une pose de départ connue ; aucune autorisation d'essai physique n'a été donnée dans cette session |
| Étalonnage des zéros servo | exige une mesure mécanique par servo ; la conversion actuelle est une convention documentée, pas une calibration |
| Vue avant (`front`) servie depuis l'Astra | demande une modification des deux services et du schéma d'outils C++ ; laissé ouvert, écart signalé dans les unités |
| `ros2_control` | chemin long (plugin matériel, relais vers le service 8001) ; le chemin court fonctionne et est mesuré |

## 6. Conditions de clôture vérifiables

1. `ros2 action list | grep controller` liste `arm_controller` et `grip_controller`.
2. `ros2 topic hz /arm/joint_states` donne 20 Hz et `/joint_states` suit ces valeurs.
3. `python3 clawbot_moveit_config/tools/plan_demo.py demo` renvoie `error_code 1` avec une durée
   strictement positive.
4. `curl 'http://127.0.0.1:8003/detect_raw?camera=claw'` renvoie HTTP 200.
5. `cd clawbot_arm_controller && ROS_DOMAIN_ID=99 pytest test -q` : 22 tests verts.
6. `python3 scripts/validate_okf.py` : 0 erreur.

## 7. Voir aussi

- Description technique : [[manipulation_moveit]]
- Bras et servos : [[bras_6dof]]
- Caméra du bras : [[camera_usb_bras]]
- Caméra RGB-D du châssis : [[orbbec_astra_pro_plus]]
- Rebranchement du même jour : [[2026-11-10_rebranchement_camera_bras]]
- Unités et dépendances : [[systemd_robot_services]]
