---
title: "Manipulation — MoveIt 2 et contrôleur de trajectoire du bras"
date: "2026-11-10T19:52:00+01:00"
author: "Hermes Agent"
tags: [software, manipulation, moveit2, bras, servo, ros2-control, action, trajectoire]
status: validé
---

# Manipulation — MoveIt 2 et contrôleur de trajectoire du bras

Chaîne de manipulation du Clawbot X3 Plus : de la planification MoveIt 2 jusqu'aux servos du
bras ([[bras_6dof]]), sans `ros2_control`. Retour à l'[[index]].

```text
MoveIt (move_group)
  └─ /arm_controller/follow_joint_trajectory   (5 axes)
     /grip_controller/follow_joint_trajectory  (pince)
        └─ clawbot_arm_controller : échantillonnage 10 Hz
             ├─ /servo_ctrl  Int32MultiArray [id_servo, angle_deg]
             │     └─ driver_node (Mcnamu_driver_X3) → carte Rosmaster → servos
             └─ /arm/joint_states  JointState (consignes, radians)
                   └─ joint_state_publisher (source_list) → /joint_states → rsp → TF
```

## 1. Composants installés

| Élément | Version / chemin | Source |
|---|---|---|
| MoveIt 2 | `moveit_core` 2.5.10 (`ros-humble-moveit-core`) | `dpkg -l` |
| Solveur de cinématique inverse | `pick_ik` 1.1.2, plugin `pick_ik/PickIkPlugin` | `dpkg -l`, `pick_ik_kinematics_description.xml` |
| `ros2_control` | 2.53.1 — installé mais **non utilisé** | `dpkg -l` |
| Nouveau paquet contrôleur | `clawbot_arm_controller` 0.1.0, ament_python | `~/clawbot/clawbot_arm_controller` |
| Nouveau paquet configuration | `clawbot_moveit_config` 0.1.0, ament_cmake | `~/clawbot/clawbot_moveit_config` |
| Espace de compilation | `~/clawbot` (colcon), installation dans `~/clawbot/install` | `colcon build --packages-select …` |
| Unités systemd | `clawbot-arm-controller.service` (actif), `clawbot-move-group.service` (optionnelle, démarrée à la demande) | `systemctl is-active` |

Compilation effectuée hors du venv Hermes, conformément au piège d'environnement documenté :

```bash
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
source /opt/ros/humble/setup.bash
colcon build --packages-select clawbot_arm_controller clawbot_moveit_config
# Summary: 2 packages finished
```

## 2. Correspondance articulation → servo

C'est le point le plus fragile de la chaîne : **le zéro mécanique de chaque servo n'est pas
identifié** (voir §2 de [[bras_6dof]]). La conversion est donc paramétrable, jamais codée en dur.

| Articulation URDF | Servo | Formule | Plage servo |
|---|---|---|---|
| `arm_joint1` … `arm_joint4` | 1 … 4 | `90 + q·57,2958` | 0–180° |
| `arm_joint5` | 5 | `90 + q·57,2958` | 0–270° |
| `grip_joint` | 6 | `180 + q·116,883` (q ∈ [−1,54 ; 0]) | 0–180° |

Paramètres : `config/arm_controller.yaml` du paquet `clawbot_arm_controller` (`arm_zero_deg`,
`arm_scale_deg_per_rad`, `arm_min_deg`, `arm_max_deg`, et les équivalents `grip_*`).

Protocole consommé par le pilote : `std_msgs/Int32MultiArray` avec `data = [id_servo, angle_deg]`
sur `/servo_ctrl` ; `Mcnamu_driver_X3.Servocallback` appelle `set_uart_servo_angle(id, angle)` pour
`id` de 1 à 6. Un message = **un** servo : le contrôleur les espace de 5 ms.

Ce que la commande **ne prouve pas** : que l'angle 90° corresponde à la position mécanique neutre.
Tant que l'offset n'est pas mesuré servo par servo, la commande est cohérente mais non calibrée.

## 3. Configuration MoveIt

| Fichier | Contenu |
|---|---|
| `config/clawbot_x3plus.srdf` | deux groupes — `arm` (chaîne `base_link` → `arm_link5`) et `gripper` (`grip_joint`) —, effecteur `gripper`, états nommés `home`, `ready`, `open`, `closed`, 35 paires `disable_collisions` |
| `config/kinematics.yaml` | `pick_ik/PickIkPlugin`, délai 50 ms, 8 tentatives |
| `config/joint_limits.yaml` | 0,5 rad/s et 1,0 rad/s² (bras), 0,3 et 0,6 (pince) ; positions limites laissées à l'URDF |
| `config/ompl_planning.yaml` | `RRTConnect` par défaut, `RRTstar`, `PRM` ; `request_adapters` avec `AddTimeOptimalParameterization` |
| `config/moveit_controllers.yaml` | `moveit_simple_controller_manager`, contrôleurs `arm_controller` et `grip_controller` en `FollowJointTrajectory` |

Le SRDF n'est pas saisi à la main : `scripts/generate_srdf.py` le déduit de l'URDF (chaînes,
adjacence 1 partout, adjacence 2 dans la chaîne du bras). Le régénérer après toute modification de
l'URDF.

## 4. Vérifications mesurées

Domaine 28, 2026-11-10 entre 19:47 et 19:52 CET.

| Vérification | Résultat | Commande |
|---|---|---|
| Serveurs d'action servis | `/arm_controller/follow_joint_trajectory`, `/grip_controller/follow_joint_trajectory` | `ros2 action list` |
| Consignes courantes | `/arm/joint_states` à 20,005 Hz | `ros2 topic hz /arm/joint_states` |
| Fusion dans `/joint_states` | valeurs de test `arm_joint1=0,11` et `arm_joint2=0,22` publiées sur `/arm/joint_states` retrouvées telles quelles dans `/joint_states` | sonde `rclpy`, contrôleur arrêté pour isoler la source |
| Planification (service) | `error_code 1`, 30 points, 2,85 s de trajectoire, 0,013 s de calcul, écart final ≤ 0,05 rad | `tools/plan_demo.py demo` |
| Chaîne complète planification + exécution | domaine isolé 99 : `error_code 1`, 41 consignes servo émises, écart final 0,029 rad pour une tolérance de 0,05 | `tools/execute_demo.py ready` |
| Exécution physique réelle | **réalisée le 2026-11-10 à 22:39-22:55 CET**, voir §4.1 | `tools/move_joint_step.py`, `ros2 action send_goal` |

### 4.1 Essais physiques du 2026-11-10 (opérateur présent, 40 cm dégagés, batterie à portée)

Pose de départ lue sur la carte : servos `[71, 156, 55, -5, 90, 149]`, firmware 3.5, 11,90 V.

| Essai | Consigne | Résultat mesuré sur la carte |
|---|---|---|
| Axe 1 en direct | 71 → 76 → 81 → 91° | 71 → 73 → 76 → **75** : axe bloqué par le support de la caméra Orbbec |
| Axe 1 en direct, sens inverse | 91 → 66° | **66°** exactement : la chaîne est exacte quand rien ne bloque |
| Axe 2 en direct | 156 → 150° | 151° (1° d'écart, servo en charge) |
| Pince en direct | 149 → 139° | **139°** |
| MoveIt plan seul | `arm_joint1` −5° | 14 points, `error_code 1`, départ = pose mesurée, aucun mouvement |
| MoveIt plan + exécution | `arm_joint1` −5° | 17 points, `error_code 1`, servo 1 : 66 → **61°** |
| MoveIt retour | `arm_joint1` +5° | servo 1 : 61 → **66°** |
| Pince par le serveur d'action | 139 → 129 → 139° | 129° puis **139°**, `SUCCEEDED` deux fois |
| Axe 4 pendant les trajectoires | — | **-5° inchangé** : l'articulation passive n'a reçu aucune consigne |
| Dégagement du support caméra | servo 2 : 156 → 146 → 137 → 127° | **127°** (demande de l'opérateur : 156° touchait le support) |

### 4.2 Deuxième série : axes 3, 4 et 5 (23:00-23:05 CET)

Le servo 4 étant rebranché et son retour d'angle redevenu valide ([[ERR-2026-11-10-007_retour_angle_servo_bras]],
clos), l'axe 4 est réintégré au groupe : `passive_joints: []`.

| Essai | Consigne | Résultat mesuré |
|---|---|---|
| Axe 4 en direct | 55 → 60° | **59°** |
| Axe 3 en direct | 55 → 50° | **50°** |
| Axe 5 en direct | 90 → 95° | **95°** |
| MoveIt, axe 3 | −5° | servo 3 : 54 → **49°**, autres axes inchangés |
| MoveIt, axe 4 | −5° | servo 4 : 55 → **49°** (consigne 50°) |
| Axe 4, `passive_joints: []` | — | la trajectoire ne le laisse plus de côté : il est commandé comme les autres |

Les six servos sont donc commandables et mesurables : axes 1, 3, 5 et pince suivent la consigne au
degré près, axes 2 et 4 accusent 1° d'écart (servos chargés).

**Piège confirmé par la mesure** : entre deux essais, le contrôleur a été redémarré avec un
instantané de pose devenu périmé (axe 3 à 54° alors que le servo était à 49°). La trajectoire
suivante, qui ne visait que l'axe 4, a ramené l'axe 3 à 53° : la position supposée fait loi pour
tous les axes portés par la trajectoire. Toute modification physique hors MoveIt doit donc être
suivie de `scripts/sync_arm_pose.py` **et** du redémarrage du contrôleur.

Conclusion mesurée : la chaîne MoveIt → action → conversion → `/servo_ctrl` → MCU → servo
fonctionne, avec une précision de **±1°** entre la consigne articulaire et l'angle relu (arrondi
au degré et bande morte du servo). Le mouvement est réversible (aller-retour à l'identique).

Incident d'essai : un script de lecture a ouvert `/dev/myserial` alors que le pilote tournait ; le
pilote a levé `device reports readiness to read but returned no data (multiple access on port?)`
et systemd l'a relancé. Les scripts `scripts/read_arm_angles.py` et `scripts/sync_arm_pose.py`
refusent désormais de s'exécuter si `ros2-driver-node.service` est actif (option `--force` pour
outrepasser, déconseillée).

Tests du paquet contrôleur, hors matériel (`ROS_DOMAIN_ID=99`, aucun abonné à `/servo_ctrl`) :

```bash
$ cd ~/clawbot/clawbot_arm_controller
$ ROS_DOMAIN_ID=99 python3 -m pytest test -q -p no:launch_testing -p no:launch_ros
23 passed, 1 warning in 9.55s
```

18 tests portent sur les fonctions pures (conversion, bornes, interpolation, refus de paramètres
incohérents), 4 sur le contrat d'action (trajectoire du bras, articulations refusées, pince,
annulation qui arrête la publication), 1 sur le mode « articulation passive » (aucune consigne ne
part vers le servo, la position reste suivie).

## 5. Défauts corrigés pendant la mise en service

| Symptôme | Cause | Correction |
|---|---|---|
| Trajectoire de 101 points, tous à `time_from_start = 0` | les adaptateurs de requête n'étaient pas chargés : `AddTimeOptimalParameterization` absent | `request_adapters` placé dans `ompl_planning.yaml` (champ **chaîne**, pas liste) ; la durée apparaît (2,85 s) |
| `AttributeError: FollowJointTrajectory_Goal has no attribute request` | le `goal_callback` reçoit la requête, pas un handle d'objectif | signature corrigée ; les tests de contrat le vérifient |
| `move_group` choisissait CHOMP | plusieurs plugins de planification chargés, aucun `planning_plugin` imposé | `planning_plugin: ompl_interface/OMPLPlanner` dans `ompl_planning.yaml` |
| `joint_state_publisher` publiait 0 pour les articulations du bras | deux éditeurs se contredisaient sur `/joint_states` | `source_list: ['/arm/joint_states']` dans `launch/robot_description.launch.py` ; vérifié par la sonde §4 |

## 6. Limites constatées

- **Aucune rétroaction** : le MCU ne publie pas la position du bras. `/arm/joint_states` contient des
  consignes, pas des mesures ; au démarrage le contrôleur suppose `initial_positions`. Procédure
  après toute coupure d'alimentation ou déplacement à la main :
  `sudo systemctl stop ros2-driver-node` → `python3 scripts/sync_arm_pose.py` →
  `sudo systemctl start ros2-driver-node` → `sudo systemctl restart clawbot-arm-controller`.
  Depuis le 2026-11-10 23:23, l'unité lit directement
  `clawbot_arm_controller/config/arm_controller.yaml` (`params_file:=…`) : la synchro ne
  demande plus de recompilation, un simple redémarrage du service suffit.
  Le fichier `config/arm_controller.yaml` porte l'instantané du 2026-11-10 23:05.
- **Servo 4 réparé, mais surveillé** : son retour d'angle était invalide (`-5°` constant) jusqu'au
  rebranchement du 2026-11-10 23:00 ([[ERR-2026-11-10-007_retour_angle_servo_bras]], clos). Le mode
  `passive_joints` existe toujours et reste la parade si le défaut revient : l'articulation est
  alors publiée dans `/arm/joint_states` sans qu'aucune consigne ne parte vers le servo.
- **L'instantané de pose fait loi** : la première trajectoire ramène chaque axe porté à la position
  supposée au démarrage du contrôleur. Un instantané périmé déplace donc des axes qu'on ne visait
  pas — constaté : axe 3 ramené de 49° à 53° par une trajectoire sur l'axe 4. Toute modification
  physique hors MoveIt exige `scripts/sync_arm_pose.py` **puis** un redémarrage du contrôleur.
- **Arrêt du pilote = cascade** : `clawbot-arm-controller.service` et `clawbot-move-group.service`
  déclarent `Requires=ros2-driver-node.service`. Relire les angles (ce qui impose d'arrêter le
  pilote) arrête donc aussi le contrôleur et move_group : les relancer après chaque lecture.
- **Le modèle ne protège pas encore** : la configuration qui a bloqué le bras (servos `76, 156, …`)
  est déclarée **valide** par MoveIt, et `compute_fk` y place le bout de chaîne à `x = +0,130` alors
  que le contact réel était sur le mât à `x = −0,044`. Les zéros servo sont une convention non
  mesurée : étalonner avant de faire confiance à la détection de collision
  ([[etalonnage_bras]]).
- **Obstacle dans l'espace de travail** : à servo 2 = 156°, l'axe 1 est bloqué par le support de la
  caméra Orbbec dès 75-76° (servo en butée, position non atteinte). Position retenue après essai :
  servo 2 = 127°. Tout retour vers 156° doit être considéré comme collision avec ce support.
- **Port série exclusif** : les scripts de lecture (`read_arm_angles.py`, `sync_arm_pose.py`)
  refusent de s'exécuter tant que `ros2-driver-node.service` tourne ; deux lecteurs se volent les
  octets et font tomber le pilote (`multiple access on port?`).
- **Pas de `ros2_control`** : la planification passe par `moveit_simple_controller_manager` et un
  serveur d'action écrit pour l'occasion. Aucun asservissement, aucune limite de couple, aucun
  contrôleur de position matériel.
- **Précision atteinte** : ±1° entre la consigne articulaire et l'angle relu (arrondi au degré,
  bande morte du servo). Un axe chargé peut rester à 1° de sa consigne.
- **Bras 5 axes** : une pose 6D arbitraire n'est pas atteignable ; `pick_ik` échoue souvent sur des
  objectifs de pose. La planification en espace articulaire fonctionne.
- **Caméra du bras sur le même index que « front »** : le seul périphérique UVC (`0c45:6340`) sert
  les deux noms dans la configuration actuelle, voir [[camera_usb_bras]].
- Durée maximale d'une trajectoire acceptée par le contrôleur : `max_duration_s: 30,0` ; au-delà,
  l'objectif est refusé (`INVALID_GOAL`) plutôt qu'exécuté à moitié.

## 7. Voir aussi

- Bras et servos : [[bras_6dof]]
- Modèle géométrique : [[modele_urdf_clawbot]]
- Caméra du bras : [[camera_usb_bras]]
- Journal de mise en service : [[2026-11-10_mise_en_service_manipulation]]
- Unités systemd : [[systemd_robot_services]]
- Pont LLM → ROS 2, qui commande déjà `/servo_ctrl` : [[llm2ros_bridge]]
