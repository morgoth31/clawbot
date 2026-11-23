# Addendum A au référentiel — SLAM 2D, navigation, saisie MoveIt 2, SLAM 3D

> Normatif pour les prompts F00 à F05. Copié dans le dépôt par F00 sous `docs/architecture/addendum_A_fonctions.md`, puis fusionné dans `docs/architecture/cible.md` par l'exigence REQ-ARCH-020.
> Version 1.0 — 2026-11-22.

## A1. Priorités

| Rang | Fonction | Prompts | Condition matérielle |
|---|---|---|---|
| 1 | SLAM 2D fiable : cartographier, sauver, relocaliser | F01 | lidar, odométrie EKF |
| 2 | Navigation sur carte et exploration autonome, au service du SLAM | F02 | F01 |
| 3 | Saisie d'objets avec MoveIt 2 | F03 (perception 3D), F04 (saisie) | bras, caméra du poignet, profondeur si disponible |
| 4 | SLAM 3D : cartes 3D de l'environnement | F05 | profondeur Astra fonctionnelle (P11), budget CPU, disque |

F00 établit l'état des lieux et les données de référence. Aucune fonction n'est déclarée disponible sans sa validation physique.

## A2. Invariants ajoutés

| ID | Invariant |
|---|---|
| INV-11 | Un seul écrivain de la transformée `map → odom` à la fois. Les capacités `mapping`, `localization` et `mapping_3d` forment le groupe exclusif `map_tf_writer`. `capability_manager` refuse d'en activer deux (`CAPABILITY_CONFLICT`). |
| INV-12 | Le bras est en enveloppe de repos (C10) avant tout déplacement de la base, y compris pendant l'exploration et l'approche d'un objet. |
| INV-13 | Toute saisie se fait à vitesse réduite (facteur de vitesse et d'accélération MoveIt ≤ 0,3), avec une scène de planification qui contient au moins le sol et le châssis. |
| INV-14 | Aucune capacité qui écrit des données volumineuses (`mapping_3d`, `record_3d`) ne démarre s'il reste moins de 10 Go libres sur `/`. |
| INV-15 | Un skill dont la validation physique n'est pas conforme est déclaré `experimental: true`. Le serveur de skills le refuse (`SKILL_NOT_VALIDATED`), sauf en domaine 99 ou pendant le **mode validation**, que seul l'opérateur active depuis le tableau de bord (8001), pour 30 min au plus. Aucun outil MCP ne peut l'activer. |

## A3. Capacités (ajouts et modifications du manifeste)

| Capacité | Contenu | Prête quand | Groupe exclusif | Remarque |
|---|---|---|---|---|
| `mapping` | `slam_toolbox` en mode `mapping` | `/map` reçu depuis moins de 30 s | `map_tf_writer` | existant, paramètres revus en F01 |
| `localization` | `slam_toolbox` en mode `localization` sur une carte sérialisée | pose publiée, covariance sous le seuil | `map_tf_writer` | nouveau (F01) |
| `navigation` | Nav2 **sans** AMCL ni `map_server` ; contrôleur holonome | action `navigate_to_pose` servie | — | requiert `mapping` **ou** `localization` ; le `Conflicts=` actuel entre `clawbot-slam` et `clawbot-nav2` disparaît (F02) |
| `mapping_3d` | RTAB-Map : lidar 2D + RGB-D + odométrie EKF, `Reg/Force3DoF` | `/rtabmap/info` reçu, carte 3D non vide | `map_tf_writer` | nouveau (F05) |
| `record_3d` | enregistrement rosbag2 limité (scan, odom, tf, RGB-D à cadence réduite) | enregistreur actif | — | compatible avec `mapping` : permet la 3D hors ligne (F05) |
| `object_perception` | détection (P12) + localisation 3D des objets | `/perception/objects` ≥ 2 Hz | — | nouveau (F03) |
| `arm` | trajectoire + MoveIt, avec pince | inchangé | — | configuration IK revue en F04 |

## A4. Skills ajoutés

| Skill | Paramètres | Capacités | Prompt |
|---|---|---|---|
| `map_save` | `name` | `mapping` ou `localization` | F01 |
| `map_load` | `name` (active `localization` sur cette carte) | — | F01 |
| `map_list` | — | — | F01 |
| `pose_name` / `navigate_to_named` | `name` (pose nommée sur la carte courante) | `navigation` | F02 |
| `explore` | `max_duration_s`, `max_distance_m`, `min_frontier_m` | `mapping`, `navigation` | F02 |
| `locate_object` | `classes`, `camera` | `object_perception` | F03 |
| `approach_object` | `object_id`, `standoff_m` | `navigation` ou `base` | F04 |
| `pick_object` | `object_id` | `arm`, `object_perception` | F04 |
| `place_object` | `target` (pose nommée ou `here`) | `arm` | F04 |
| `map3d_save`, `map3d_export` | `name`, `format` (`ply`, `octomap`) | `mapping_3d` | F05 |
| `map3d_from_recording` | `recording`, `name` | — (traitement hors ligne) | F05 |

## A5. Codes d'erreur ajoutés (table §6.1, à valider par l'opérateur dans le prompt concerné)

| Catégorie | Code | Relance auto | Décisions autorisées |
|---|---|---|---|
| SENSOR | `LOCALIZATION_LOST` | non | `RETRY_STEP` après `map_load`, `REPLACE_REMAINING`, `ABORT` |
| EXECUTION | `EXPLORATION_INCOMPLETE` | non | `RETRY_WITH_PARAMS`, `SKIP_STEP`, `ABORT` |
| EXECUTION | `OBJECT_NOT_FOUND` | non | `RETRY_WITH_PARAMS` (autre caméra, autre point de vue), `REPLACE_REMAINING`, `ABORT` |
| EXECUTION | `OBJECT_UNREACHABLE` | non | `REPLACE_REMAINING` (insérer `approach_object`), `ABORT` |
| PRECONDITION | `DISK_LOW` | non | `ABORT` seulement ; prévenir l'opérateur |
| PRECONDITION | `SKILL_NOT_VALIDATED` | non | `REPLACE_REMAINING` sans ce skill, `ABORT` |

## A6. Interfaces ajoutées

| Nom | Type | Éditeur | Remarque |
|---|---|---|---|
| `/perception/objects` | `vision_msgs/Detection3DArray`, repère `base_link` | `object_locator` (F03) | un identifiant stable par objet, durée de vie 5 s sans nouvelle observation |
| `/clawbot/maps/current` | `std_msgs/String` (JSON), TRANSIENT_LOCAL | `map_manager` (F01) | nom de la carte courante, mode, date |
| `/clawbot/grasp/state` | `std_msgs/String` (JSON) | `skill_server` (F04) | phase de saisie, pour le feedback |

## A7. Données

| Chemin | Contenu |
|---|---|
| `/var/lib/clawbot/maps/<nom>/` | `map.posegraph`, `map.data` (sérialisation slam_toolbox), `map.pgm`, `map.yaml`, `meta.json` (date, mission, poses nommées) |
| `/var/lib/clawbot/maps3d/<nom>/` | `rtabmap.db`, exports `cloud.ply`, `octomap.bt`, `meta.json` |
| `/var/lib/clawbot/recordings/<nom>/` | enregistrements rosbag2 de `record_3d` |
| `/var/lib/clawbot/test_data/` | données de référence enregistrées en F00, rejouées dans les tests du domaine 99 ; inventaire versionné dans `tests/data_manifest.yaml` (chemin, taille, sha256) |

## A8. Validation physique

Chaque exigence de niveau `hardware` se vérifie par une procédure `tests/hardware/HW-<DOMAINE>-<NNN>.md`, au modèle du skill `clawbot-dev-cycle` (`templates/hw_validation.md`). Le fichier rempli se termine par une ligne `Verdict : CONFORME` ou `Verdict : NON CONFORME`. `trace_check.py` refuse le statut `verified` d'une exigence matérielle sans ce verdict conforme dans sa preuve.

Qui exécute :
- **Hermes, par les outils MCP** (missions et skills de haut niveau uniquement) quand la procédure le prévoit et que l'opérateur a confirmé sa présence, la zone dégagée et l'accès à l'arrêt d'urgence ;
- **l'opérateur seul** pour toute étape de bas niveau (publication directe, coupure d'alimentation, manipulation du robot).
