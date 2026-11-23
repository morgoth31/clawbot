# État des lieux — fonctions SLAM 2D, saisie MoveIt 2, SLAM 3D (F00)

**Date :** 2026-11-22 · **Branche :** `docs/REQ-ARCH-020-fonctions` · **Mode :** DÉVELOPPEMENT
**Mesures :** lecture seule en domaine 28, robot non sollicité.

## 0. Ce qui bloque, en tête

**Les enregistrements de référence du §4.2 n'ont pas été faits.** Ils demandent l'opérateur
au volant et une pièce libre ; la session s'est arrêtée avant. Conséquence : `rgbd_statique`
et `objets_table` n'existent pas, donc **le SLAM 3D et la saisie ne peuvent pas encore être
testés en domaine 99** sur des données réelles. Les trois jeux sont déclarés dans
`tests/data_manifest.yaml` avec `enregistre: false`, et le test d'inventaire **s'ignore** au
lieu d'échouer.

**Prérequis partiellement tenus** : C01 à C04 sont fusionnés (`rel-C01` à `rel-C04`
présents), **mais P14b n'est pas fusionné** (`rel-P14` absent) — il est bloqué sur le cliquet
de lint, et P15/P16 ne le sont pas non plus. `smoke_check.sh` n'a donc pas été rejoué après
un déploiement qui n'a pas eu lieu : la production est toujours sur `prod-20261122-p13`.

## 1. Tableau de décision

| Fonction | Verdict | Bloquants | Ce qu'il faut installer ou réparer |
|---|---|---|---|
| **SLAM 2D** | **FAISABLE** | aucun pour la cartographie seule | rien : `slam_toolbox` tourne (résolution 0,05 m, `map_update_interval` 2,0 s, `minimum_travel_distance` 0,2 m, boucle fermée active), `/scan` 10 Hz, EKF et IMU présents |
| **Navigation et exploration** | **FAISABLE AVEC RÉSERVE** | `mapping` et `navigation` sont mutuellement exclusifs ; le conflit SLAM/Nav2 n'est refusé proprement que depuis C04, **non déployé** | rien d'absent : `nav2_bringup` et `nav2_mppi_controller` sont installés. Il faut déployer C04 avant d'explorer |
| **Saisie MoveIt 2** | **FAISABLE AVEC RÉSERVE** | pas de client Python (`pymoveit2`, `moveit_py` absents) ; **HW-ARM-001 n'a jamais été exécuté** (P13 s'est arrêté avant la validation physique) ; `move_group` n'est pas démarré par défaut | `pymoveit2` (dépôt GitHub, pip/source) ou `ros-humble-moveit-py` ; les poses nommées validées ; la procédure HW-ARM-001 |
| **SLAM 3D** | **FAISABLE AVEC RÉSERVE** | la profondeur fonctionne (21,3 Hz, 640×480, `plumb_bob`) mais **`camera_info.d` est nul** : intrinsèques non calibrées ; aucun jeu `rgbd_statique` enregistré | `rtabmap_ros`, `rtabmap_slam`, `rtabmap_util` et `octomap_server` sont **déjà installés**. Il faut calibrer l'Astra (`camera_calibration` est présent) et enregistrer les jeux |

**La profondeur n'est donc pas bloquante** : contrairement à l'hypothèse du prompt, E01
montre qu'elle publie. Le SLAM 3D est *faisable*, sous réserve de calibration et de données.

## 2. État des lieux (mesures)

| ID | Mesure | Résultat |
|---|---|---|
| E01 | `/camera/depth/image_raw` | **21,3 Hz** sur 12 s ; `camera_info` 17,8-20,3 Hz ; 640×480 ; `distortion_model: plumb_bob` ; **`D` = 0** (aucune distortion, donc calibration par défaut) |
| E02 | TF `base_link → camera_link` | translation `[-0,044, 0,000, 0,420]` (statique) |
| E02 | TF `base_link → camera_color_optical_frame` | `[-0,046, 0,025, 0,419]` |
| E02 | TF `arm_link5 → wrist_camera_optical_frame` | `[-0,046, -0,002, -0,123]` |
| E03 | Groupes du SRDF | `arm`, `gripper` (groupe séparé) ; effecteur `gripper` sur `arm_link5` |
| E03 | Solveur IK | **`pick_ik/PickIkPlugin`** |
| E03 | Contrôleurs | deux `FollowJointTrajectory` (bras et pince) |
| E04 | Paquets présents | `rtabmap_ros`, `rtabmap_slam`, `rtabmap_util`, `pick_ik`, `nav2_bringup`, `nav2_mppi_controller`, `vision_msgs`, `octomap_server`, `rosbag2_compression_zstd`, `camera_calibration`, `topic_tools`, `message_filters` |
| E04 | Paquets absents | `pymoveit2`, `moveit_py` |
| E05 | Disque | 94 Go utilisés / 147 Go, **47 Go libres** (68 %) ; `/var/lib/clawbot` = 716 Ko |
| E05 | RAM | 6 291 Mo utilisés sur 15 655, 8 903 disponibles |
| E06 | `slam_toolbox` | résolution **0,05**, `map_update_interval` **2,0 s**, `minimum_travel_distance` **0,2 m**, `do_loop_closing` **True** |
| E07 | Dérive odométrique sur 360° | **non mesurée** — exige que l'opérateur fasse tourner le robot (§4.2) |

## 3. Référentiel et outils

- `docs/architecture/addendum_A_fonctions.md` : copié depuis `~/clawbot-fonctions/`.
- `cible.md` §1 : INV-11 à INV-15 ajoutés, avec renvoi vers l'addendum.
- `scripts/trace_check.py` remplacé par la version 1.2.0 du skill (domaines à chiffres comme
  `MAP3D`, verdict des validations physiques) ; les deux copies ont le même sha256.
- Exigences : REQ-ARCH-020 (inspection), REQ-TEST-020 (intégration, `draft`), REQ-TEST-021
  (unitaire, implémentée).

## 4. Tests

| Test | Résultat |
|---|---|
| `tests/test_addendum_a.py` (REQ-ARCH-020) | 2 passés |
| `tests/test_data_manifest.py` (REQ-TEST-021) | 1 passé, **1 ignoré** — « données de référence absentes : voir F00 » |

## 5. Ce qu'il reste à faire, dans l'ordre

1. **Enregistrer les trois jeux** avec l'opérateur : `slam2d_piece` (3-5 min, tour de pièce),
   `rgbd_statique` (60 s, distances au mètre ruban), `objets_table` (60 s, trois objets,
   positions mesurées par rapport à `base_link`). Vérifier 15 Go libres avant (47 Go
   aujourd'hui), `ros2 bag record -a` avec compression `zstd`.
2. **Mesurer E07** pendant `slam2d_piece` : pose `/odom` avant et après un 360°.
3. **Calibrer l'Astra** (`camera_calibration` installé) : `D` nul signifie intrinsèques par
   défaut, ce qui suffit pour un nuage mais pas pour une mesure métrique.
4. **Débloquer P14b** (25 défauts de lint dans `hardware_service.py`) puis déployer C04, sans
   quoi le conflit SLAM/Nav2 redeviendra silencieux.
5. **HW-ARM-001** avant toute saisie : les poses nommées ne sont pas validées.

## 6. Sécurité

- Publication en domaine 28 : **non**. Uniquement `ros2 topic hz`, `ros2 topic echo --once`,
  `ros2 param get` et `tf2_echo` en lecture.
- `/etc` et unités : **non touchés**.
- Arbre de production : détaché sur `prod-20261122-p13`, `git status` vide.
- Aucun processus laissé en vie.
