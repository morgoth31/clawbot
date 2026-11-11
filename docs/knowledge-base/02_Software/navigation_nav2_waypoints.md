---
title: "Navigation Nav2 sur carte : catalogue de waypoints fermé, unités clawbot-ekf et clawbot-nav2"
date: "2026-11-11T16:17:13+01:00"
author: "Hermes Agent"
tags: [software, ros2, nav2, amcl, waypoints, navigation, directeur, systemd]
status: validé
---

# Navigation Nav2 sur carte — lot 5

Mise en service de la navigation sur carte sauvegardée, et fermeture de la seule porte par
laquelle une coordonnée libre pouvait entrer dans le système. Retour à l'[[index]] ; conception :
[[directeur_s1]] ; cartographie : [[slam_cartographie]] ; état antérieur de la chaîne :
[[ros2_nav_stack]].

```text
S2 (Telegram / MCP)                 S1                          matériel
  start_skill                      DIRECTEUR
  skill=navigate_to   ──────────►  skills.py : nom -> goal
  args={destination: "est"}        NavigateToPose(map, x, y, yaw)
                                          │
                                          ▼
                                   Nav2 : bt_navigator -> planner -> controller
                                          │  /cmd_vel
                                          ▼
                                   ARBITRE 20 Hz ── /cmd_vel_safe ── driver ── roues
                                   (obstacle < 0,15 m -> zéro)
```

## 1. Ce qui est déployé

| Élément | Chemin | État |
|---|---|---|
| Catalogue de waypoints | `config/waypoints.yaml` | 3 waypoints nommés, énumération fermée |
| Résolution nom → pose | `clawbot_director/clawbot_director/waypoints.py` | chargé et validé, refus des coordonnées |
| Adaptateur du skill | `clawbot_director/clawbot_director/skills.py` | `navigate_to` → `/navigate_to_pose` |
| Paramètres Nav2 | `config/nav2_clawbot.yaml` | AMCL + NavFn + Regulated Pure Pursuit |
| Lancement | `launch/navigation.launch.py` | carte déduite du catalogue |
| Unité EKF | `clawbot-ekf.service` | `active`, `/odom` 10 Hz, TF `odom → base_link` |
| Unité navigation | `clawbot-nav2.service` | `active`, 12 nœuds Nav2 actifs |
| Base virtuelle | `scripts/simu_base_virtuelle.py` | domaine 99 uniquement |
| Preuve de bout en bout | `scripts/preuve_navigation_99.py` | 3 waypoints atteints, écart ≤ 0,121 m |
| Pose initiale AMCL | `scripts/poser_pose_initiale.py` | refuse tout domaine autre que 28 |

## 2. Catalogue de waypoints

Les waypoints sont mesurés sur la carte `test_cartographie_apres_deplacement`
(177 × 80 cellules, résolution 0,05 m, origine `[-0,783, -2,67]`).

| Nom | x (m) | y (m) | yaw (rad) | Dégagement mesuré | Justification |
|---|---|---|---|---|---|
| `ouest` | 1,50 | −0,30 | 0,00 | 0,65 m | zone dégagée côté ouest, point de repli et de départ |
| `centre` | 2,50 | 0,00 | 0,00 | 1,05 m | centre de la pièce, le plus dégagé |
| `est` | 5,30 | 0,48 | 0,00 | 0,75 m | côté est, au-delà du passage entre deux obstacles |

Distances : `ouest → centre` 1,08 m ; `centre → est` 2,85 m ; `ouest → est` 3,87 m. Les trois
appartiennent à la même composante connexe praticable (dégagement ≥ 0,30 m), vérifié par test.

Le dégagement est la distance à la première cellule non navigable, **bord de carte compris** :
sans cette précaution, les coins de la zone non observée passaient pour les points les plus sûrs
de la carte.

## 3. Contrat d'entrée de `navigate_to`

| Cas | Comportement | Code |
|---|---|---|
| `{"destination": "est"}` | goal `NavigateToPose` en `map`, pose du catalogue | `ACCEPTED` |
| `{"destination": "cuisine"}` | refus, la liste des noms connus est renvoyée | `INVALID` |
| `{"x": 1.0, "y": 2.0}` | refus, motif « coordonnées libres refusées » | `INVALID` |
| `{"destination": {"x": 1, "y": 2}}` | refus | `INVALID` |
| `{"destination": "est", "pose": …}` | refus, la clé de pose suffit à faire échouer l'appel | `INVALID` |
| `timeout_s` hors `[1, 120]` | refus | `INVALID` |
| absent du catalogue au chargement | `CatalogueInvalide` au démarrage, aucun goal | — |

Le refus a lieu dans `skills.py`, avant qu'un goal existe : c'est le seul point du système où un
nom devient une pose, il ferme la porte plutôt que de filtrer après coup.

## 4. Paramètres Nav2 et pourquoi ces valeurs

| Paramètre | Valeur | Raison mesurée |
|---|---|---|
| `max_velocity` (lissage) | 0,10 m/s | vitesse linéaire mesurée proportionnelle jusque 0,10 (consigne 0,10 → 0,102) |
| `desired_linear_vel` | 0,09 m/s | marge sous le maximum tenable |
| `max_accel` | 0,30 m/s² | temps mort de la base ~0,85 s : une rampe plus vive fait osciller le régulateur |
| `xy_goal_tolerance` | 0,12 m | critère de sortie du lot à ±0,20 m : la tolérance doit être plus fine |
| `robot_radius` | 0,16 m | châssis de 20 cm de côté |
| `inflation_radius` | 0,35 m | marge de passage dans une pièce de 4 m de long |
| `laser_max_range` (AMCL) | 12,0 m | portée utile de la pièce (TG30), jamais 100 m par défaut |
| largeur/hauteur du costmap local | 3 × 3 cellules | `nav2_costmap_2d` les attend en **entier** ; `3.0` fait échouer la construction du nœud |

## 5. Mesures

### 5.1 Preuve de bout en bout en simulation (domaine 99)

Base virtuelle publiant `/odom` (20 Hz), la TF `odom → base_link` et un `/scan` à 8 Hz fabriqué par
lancer de rayons sur le fichier de carte réel ; Nav2 lancé avec **les paramètres du robot** ;
directeur réel alimenté en `/safety/state = OK`.

```text
Nav2 pret en 6.5 s
  ouest    pose [1.5, -0.3, 0.0]        cible [1.5, -0.3]        ecart 0.000 m  OK
  centre   pose [2.406, -0.076, 0.293]  cible [2.5, 0.0]          ecart 0.121 m  OK
  est      pose [5.37, 0.523, 0.233]    cible [5.3, 0.48]         ecart 0.082 m  OK
etat final : DONE etape 3/3
```

Commande :

```bash
cd /home/jetson/clawbot && export ROS_DOMAIN_ID=99
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
source /opt/ros/humble/setup.bash && source install/setup.bash
python3 scripts/preuve_navigation_99.py
```

L'écart de `centre` (0,121 m) est la tolérance d'arrivée de Nav2 elle-même : la mesure est bornée
par le réglage, pas par la simulation.

### 5.2 Ce que la simulation ne prouve pas

| Non couvert | Pourquoi | Où cela se mesure |
|---|---|---|
| Adhérence, glissement des roues Mecanum | base virtuelle cinématique | essai physique, robot au sol |
| Temps mort de la base (0,85 s) | non modélisé | essai physique |
| Justesse d'AMCL sur un scan réel | scan synthétique | essai physique, écart mesuré au mètre ruban |
| Détection d'obstacle de l'arbitre pendant une navigation Nav2 | l'arbitre n'est pas dans la boucle de simulation | essai physique, obstacle posé devant |

## 6. Essai physique — protocole

```bash
# 1. le robot est posé sur un waypoint connu, bras replié, dégagement mesuré
systemctl is-active ros2-driver-node clawbot-ekf clawbot-nav2 clawbot-safety-arbitrator

# 2. déclarer la pose réelle (le catalogue refuse un nom inconnu)
export ROS_DOMAIN_ID=28
python3 /home/jetson/clawbot/scripts/poser_pose_initiale.py ouest

# 3. vérifier la chaîne avant de bouger
ros2 run tf2_ros tf2_echo map base_link       # pose ≈ celle du waypoint, à ±20 cm
ros2 topic echo /safety/state --once          # OK
ros2 topic hz /scan                           # ~10 Hz

# 4. un seul waypoint d'abord, pas la séquence
echo '{"op":"start_skill","skill":"navigate_to","args":{"destination":"centre"}}' \
  | python3 -m bridge_mcp.director_client

# 5. suivre l'arrivée, puis mesurer au sol l'écart réel
echo '{"op":"get_task"}' | python3 -m bridge_mcp.director_client
```

`clawbot-slam` et `clawbot-nav2` se déclarent mutuellement `Conflicts=` : SLAM Toolbox en
cartographie publie `map → odom`, AMCL aussi, et deux écrivains pour une transformation est le
même défaut que deux éditeurs pour `/cmd_vel`.

## 7. Défauts corrigés pendant ce lot

| Défaut | Cause réelle | Correctif |
|---|---|---|
| Aucune odométrie publiée, TF `odom` absente | le filtre EKF n'était lancé par aucune unité ; il avait été démarré à la main | `clawbot-ekf.service` |
| `ekf_node` du paquet Debian refuse de démarrer | il linke `libdiagnostic_updater.so`, absente en Humble (bibliothèque header-only) | binaire du workspace constructeur + `LD_LIBRARY_PATH` sur ses bibliothèques |
| `clawbot-slam` invisible du graphe | unité lancée en **root** : découverte DDS isolée (défaut déjà connu, unité non corrigée) | `User=jetson` |
| `controller_server` meurt à la construction | `width`/`height` du costmap local écrits `3.0`, attendus entiers | `width: 3`, `height: 3` |
| Un goal envoyé trop tôt est refusé | le serveur d'action existe avant l'activation du cycle de vie | la preuve attend `lifecycle_manager_*/is_active` |
| `navigate_to` démarrait bras en extension | la précondition du directeur était un *callable* « toujours vrai » | bras replié mesuré sur `/arm/servo_angles`, voir [[preconditions_mouvement]] |
| Un arrêt du directeur laissait la tâche `RUNNING` | aucun `ExecStop` : le goal survivait sans personne pour l'attendre | `scripts/annuler_tache_service.sh`, motif `arret_service` |
| Le contexte MCP annonçait `/scan` et `/odom` absents | liste d'absences codée en dur, datée du 2026-11-10 | dérivée de l'observation (`absences_structurelles`) |

## 8. Tests

32 tests ajoutés, 268 au total, tous verts en domaine 99 :

| Fichier | Ce qui est prouvé |
|---|---|
| `clawbot_director/test/test_waypoints.py` | chargement, refus des coordonnées libres, 8 catalogues malformés refusés, cohérence géométrique avec la carte, connexité des waypoints |
| `clawbot_director/test/test_navigate_skill.py` | goal exact (cadre, pose, yaw, délai), refus des poses libres, séquence de 3 waypoints exécutée contre un faux serveur `NavigateToPose`, échec propagé, annulation par la sécurité |
| `clawbot_director/test/test_nav2_config.py` | la carte chargée est celle du catalogue, cadres du robot, tolérance sous le critère du lot, vitesses tenables, pose initiale sur un waypoint |

```bash
cd /home/jetson/clawbot && export ROS_DOMAIN_ID=99
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME; export PATH=/usr/bin:/bin:/usr/sbin:/sbin
source /opt/ros/humble/setup.bash && source install/setup.bash
python3 -m pytest tests/mcp_bridge clawbot_safety/test clawbot_arm_controller/test \
  clawbot_director/test clawbot_sentinel/test tests/test_ekf_config.py \
  tests/test_cmd_vel_scaling.py tests/test_measure_odom_drift.py \
  tests/test_servo_round_robin.py -p no:launch_testing -p no:launch_ros \
  -o addopts="" -q
# 268 passed
```

## 9. Surface MCP exposée à S2

`capabilities` publie désormais l'énumération fermée, pour que S2 n'ait pas à la deviner :

```json
"waypoints": {"centre": [2.5, 0.0], "est": [5.3, 0.48], "ouest": [1.5, -0.3]},
"navigation": {"map": "test_cartographie_apres_deplacement", "frame": "map",
               "action": "/navigate_to_pose", "xy_goal_tolerance_m": 0.12,
               "max_linear_ms": 0.10, "timeout_s": 90.0,
               "requires": ["/odom", "/scan", "tf map->odom->base_link"]}
```

La liste est lue dans `config/waypoints.yaml`, pas recopiée : une divergence entre ce que S2 voit
et ce que S1 applique est impossible par construction.

## 10. Reste ouvert

| Point | Gravité | Détail |
|---|---|---|
| Essai physique des 3 waypoints | bloquant la clôture du lot | dépend de la présence de l'opérateur |
| Enveloppe du bras non validée par l'opérateur | moyen | la précondition refuse un bras hors de la pose de repos mesurée, mais cette pose n'a pas été validée bras libre — voir [[preconditions_mouvement]] |
| Modèle 3D du bras dans le costmap | moyen | Nav2 ne voit le bras que par un rayon d'encombrement : la précondition compense à l'entrée, elle ne modélise pas le volume balayé |
| `map → odom` sans AMCL correcte | moyen | si la pose initiale est fausse, Nav2 planifie depuis une position imaginaire ; le symptôme est un premier goal refusé par le costmap |
| Carte de 8,4 m² praticables seulement | faible | la pièce est petite : les waypoints sont peu nombreux, toute extension demande une nouvelle cartographie |

## Voir aussi

- [[index]]
- [[ros2_nav_stack]]
- [[slam_cartographie]]
- [[directeur_s1]]
- [[systeme1_arbitre]]
- [[mcp_hermes]]
- [[systemd_robot_services]]
- [[inventaire_materiel]]
- [[preconditions_mouvement]]
