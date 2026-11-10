---
title: "Tests de cartographie 2D — 2026-11-10"
date: "2026-11-10T13:05:00+01:00"
author: "Hermes Agent"
tags: [operations, cartographie, slam, slam_toolbox, lidar, odometrie, test]
status: validé
---

# Tests de cartographie 2D — 2026-11-10

Deux essais de cartographie sur le robot réel, dans un couloir d'appartement : un essai **statique** (robot immobile) et un essai **avec déplacement**. Objectif : valider la chaîne `/scan` → SLAM → `/map` → fichier de carte, et mesurer ce qu'elle produit. Retour à l'[[index]] ; capteur : [[ydlidar_tg30]] ; chaîne cible : [[ros2_nav_stack]].

## 1. Moyens mis en œuvre

| Élément | Valeur |
|---|---|
| SLAM | `slam_toolbox` (nœud `async_slam_toolbox_node`), mode `mapping` |
| Paramètres | `/home/jetson/clawbot/config/slam_toolbox_mapping.yaml` (résolution 0,05 m, portée laser 12 m, `base_frame: base_footprint`, `odom_frame: odom`) |
| Source laser | `/scan`, YDLIDAR TG30, 2 020 points, 10,1 Hz, `BEST_EFFORT` |
| Odométrie | aucune nativement : nœud `scripts/odom_from_vel.py` (intègre `/vel_raw` et le lacet de `/imu/data_raw`, publie `/odom` et TF `odom → base_footprint`) |
| Carte sauvegardée | `ros2 run nav2_map_server map_saver_cli` |

Le lidar publie en `BEST_EFFORT` : un abonné en `RELIABLE` ne reçoit rien (erreur constatée au premier essai, cf. [[ydlidar_tg30]] §4). `slam_toolbox` et les scripts de test utilisent donc `qos_profile_sensor_data`.

## 2. Essai 1 — cartographie statique

Robot immobile, TF `odom → base_footprint` statique à l'identité, SLAM lancé 25 s.

| Grandeur | Valeur mesurée |
|---|---|
| Grille | 164 × 75 cellules à 0,05 m (8,20 × 3,75 m) |
| Cellules occupées | 262 |
| Cellules libres | 3 961 |
| Cellules inconnues | 8 077 |
| Emprise des cellules occupées | x 0,00 → 7,70 m ; y 0,00 → 3,70 m |
| Cadence `/map` | 1,0 Hz |
| TF `map → odom` | publiée, identité |
| Fichiers | `maps/test_cartographie_statique.pgm` + `.yaml` (12 314 octets de PGM) |

Une pose unique ne peut pas produire autre chose qu'une coupe du couloir : le résultat prouve que la chaîne fonctionne, pas qu'elle localise.

## 3. Essai 2 — déplacement aller-retour

Consigne publiée sur `/cmd_vel` : `linear.x = 0,12 m/s` pendant 2,0 s, puis `-0,10 m/s` pendant 2,0 s, avec arrêt de sécurité si le secteur frontal (±15°) descendait sous 0,50 m. Déplacement attendu : 0,24 m.

| Grandeur | Valeur mesurée |
|---|---|
| Déplacement odométrique aller | **1,659 m** (au lieu de 0,24 m) |
| Déplacement odométrique retour | 1,608 m |
| Position finale | (−0,051 ; +0,003) m — retour à 5 cm du point de départ |
| Dégagement frontal avant/après | 3,97 m / 3,97 m (aucun obstacle approché) |
| Grille après déplacement | 177 × 80 cellules à 0,05 m (8,85 × 4,00 m) |
| Cellules occupées | **1 010** (contre 262) |
| Cellules libres | **5 500** (contre 3 961) |
| Fichiers | `maps/test_cartographie_apres_deplacement.pgm` + `.yaml` (14 174 octets) |

La carte s'enrichit de façon cohérente avec un déplacement d'environ 1,6 m : 748 cellules occupées et 1 539 cellules libres supplémentaires, emprise élargie de 0,65 m en x et 0,25 m en y.

## 4. Défaut découvert : la commande de vitesse n'est pas proportionnelle

Mesure indépendante, consigne `linear.x = 0,10 m/s` pendant 1,5 s, relevé de `/vel_raw` :

```
consigne 0.10 m/s -> vel_raw x moyen -0.177 m/s (min -1.079 max 0.000, 24 echantillons)
echantillons: [0.0, 0.0, 0.0, -0.011, -0.023, -0.034, -0.073, -0.15, -0.235, -0.394, -0.796, -1.079]
```

Deux écarts, tous deux bloquants pour la navigation :

1. **Signe** : une consigne positive produit une vitesse rapportée **négative**.
2. **Échelle** : la vitesse rapportée atteint `1,079 m/s` pour une consigne de `0,10 m/s`, soit un facteur d'environ 10,8 ; l'odométrie a intégré `1,659 m` pour `0,24 m` commandés.

Aucune conclusion sur la direction physique réelle n'est tirée ici : seul le signe de la vitesse **rapportée** est mesuré, pas le sens du déplacement. Trace complète et conditions de clôture : [[ERR-2026-11-10-009_commande_vitesse_non_proportionnelle]].

Conséquence pour ce test : l'arrêt de sécurité frontal n'a jamais été déclenché, le couloir étant dégagé sur 3,97 m. Dans un espace encombré, la même commande aurait produit un déplacement huit fois plus long que prévu.

## 5. Limites de ces essais

- Aucune mesure de vérité terrain (mètre ruban, marque au sol) : les distances sont celles de l'odométrie, non validées.
- Aucune boucle fermée testée : l'aller-retour revient au point de départ mais aucune détection de fermeture n'a été observée dans les journaux.
- Qualité métrique de la carte non évaluée (superposition de scans, épaisseur des murs).
- Un seul environnement, un seul capteur, une seule session.
- Le nœud d'odométrie dérive : intégration d'Euler à 10 Hz, sans fusion avec les encodeurs bruts.

## 6. Reproduire

```bash
export ROS_DOMAIN_ID=28 && source /opt/ros/humble/setup.bash
# odométrie (à défaut d'odométrie native)
python3 /home/jetson/clawbot/scripts/odom_from_vel.py &
# SLAM
ros2 run slam_toolbox async_slam_toolbox_node --ros-args \
  --params-file /home/jetson/clawbot/config/slam_toolbox_mapping.yaml &
# sauvegarde
ros2 run nav2_map_server map_saver_cli -f /home/jetson/clawbot/maps/<nom>
```

## 7. Voir aussi

- Lidar et QoS : [[ydlidar_tg30]]
- Nœud de conduite et `/vel_raw` : [[yahboomcar_bringup_driver_node]]
- Chaîne de navigation et prérequis : [[ros2_nav_stack]]
- Défaut de commande de vitesse : [[ERR-2026-11-10-009_commande_vitesse_non_proportionnelle]]
- Modèle et TF : [[modele_urdf_clawbot]]
