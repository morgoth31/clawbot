---
title: "Cartographie SLAM — cause du silence, carte obtenue et service"
date: "2026-11-11T12:00:00+01:00"
author: "Hermes Agent"
tags: [software, slam, cartographie, nav2, lidar, tf]
status: validé
---

# Cartographie SLAM — de l'échec silencieux à la carte

Retour à l'[[index]] ; odométrie : [[mcp_hermes]] n'en traite pas, voir [[inventaire_materiel]].

## 1. Le symptôme

`slam_toolbox` tournait, publiait `/map` (1 éditeur), mais :

- aucun message ne sortait de `/map`, `map_saver` échouait ;
- la TF `map → odom` restait **exactement à l'identité** sur tout le trajet ;
- la carte ne contenait rien, malgré deux aller-retours de 1,3 m avec rotation de 180°.

`map → odom` figée à l'identité est la signature : le scan matching n'a jamais traité un seul scan.

## 2. La cause

Le nœud tournait avec `base_frame = base_footprint`, une frame **qui n'existe pas** sur ce robot
(la racine est `base_link`). Chaque scan était donc rejeté silencieusement.

Le fichier de paramètres passé au lancement avait été ignoré : `online_async_launch.py` impose ses
propres valeurs par défaut, et `slam_params_file` ne les remplace pas comme attendu. Vérification :

```bash
ros2 param get /slam_toolbox base_frame     # renvoyait : base_footprint
```

## 3. Le correctif

Lancer le nœud directement, sans passer par le lancement :

```bash
ros2 run slam_toolbox async_slam_toolbox_node --ros-args \
  -p base_frame:=base_link -p odom_frame:=odom -p map_frame:=map \
  -p scan_topic:=/scan -p mode:=mapping -p use_sim_time:=false \
  -p resolution:=0.05 -p minimum_travel_distance:=0.2 -p minimum_travel_heading:=0.2
```

Unité systemd : `services/clawbot-slam.service` (déployée sur le poste).
Deux points appris à cette occasion :

- `Environment=HOME=/home/jetson` est **obligatoire**, sinon rclpy échoue au démarrage avec
  `Failed to get logging directory` (statut 250) ;
- l'unité `Requires=ros2-driver-node.service` : sans le driver, pas de `/odom`, donc pas de TF.

## 4. Le résultat mesuré

Aller-retour de 2 × 1,3 m avec rotation de 180°, piloté par `scripts/slam_run.py` :

| Mesure | Valeur |
|---|---|
| Carte | 161 × 130 cellules à 0,05 m = **8,1 × 6,5 m** |
| Cases libres | 27 % |
| Cases occupées | 2,8 % |
| Cases inconnues | 70 % |
| `map → odom` après le trajet | **(0,068 ; 0,231)** au lieu de (0,0) |
| Fichiers | `docs/assets/maps/carte_clawbot.{pgm,png,yaml}` |

La correction de 24 cm appliquée par le scan matching sur un aller-retour de 2,6 m correspond à
l'erreur d'odométrie accumulée : la chaîne `encodeurs+gyro → odom` puis `/scan → map→odom` fonctionne.

![Carte du couloir](../assets/maps/carte_clawbot.png)

La carte est **incomplète par construction** : 70 % d'inconnu pour un couloir parcouru en ligne
droite avec une seule rotation. Le lidar ne voit que ce qu'il balaie, et le scan matching a besoin de
plusieurs orientations au même endroit pour contraindre la géométrie.

## 5. Ce qui reste à faire

1. Densifier : abaisser `minimum_travel_distance` à 0,1 et tourner sur place en plusieurs points.
2. Passer en `mode:=localization` avec la carte sauvegardée, pour que Nav2 la consomme.
3. Vérifier la stabilité de `clawbot-slam.service` sur plusieurs redémarrages (le nœud n'apparaissait
   pas dans `ros2 node list` lors du dernier contrôle, alors que `/map` avait un éditeur : à
   confirmer avant de s'appuyer dessus).

## 6. Reproduction

```bash
# cartographie
sudo systemctl restart clawbot-slam.service
ROS_DOMAIN_ID=28 python3 scripts/slam_run.py --leg 1.3 --speed 0.05
# sauvegarde dans la documentation
bash scripts/save_map.sh docs/assets/maps/carte_couloir
```
