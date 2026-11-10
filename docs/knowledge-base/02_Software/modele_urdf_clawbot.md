---
title: "Modèle URDF du Clawbot X3 Plus — description, TF et corrections"
date: "2026-11-10T11:56:00+01:00"
author: "Hermes Agent"
tags: [software, urdf, tf, robot_state_publisher, lidar, tg30, geometrie]
status: actif
---

# Modèle URDF du Clawbot X3 Plus — description, TF et corrections

Description géométrique chargée sur le robot. Retour à l'[[index]] ; matériel décrit : [[rosmaster_x3_mcu]], [[orbbec_astra_pro_plus]], [[ydlidar_tg30]], [[bras_6dof]].

## 1. Fichier et lancement

| Élément | Valeur |
|---|---|
| Fichier actif | `/home/jetson/clawbot/urdf/clawbot_x3plus.urdf` (surchargeable par `CLAWBOT_URDF`) |
| Lanceur | `/home/jetson/clawbot/launch/robot_description.launch.py` |
| Unité systemd | `clawbot-description.service` (`robot_state_publisher` + `joint_state_publisher`) |
| Contenu | 21 liens, 20 joints, racine `base_footprint` |
| Validation | `python3 urdf/validate_urdf.py urdf/clawbot_x3plus.urdf` → arbre continu, aucune erreur (2026-11-10 11:39 CET) |

Le fichier est un export de CAO retravaillé : masses et inerties proviennent du modèle d'origine, les valeurs du lidar ont été remplacées (voir §4).

## 2. Transformations fixes publiées

| Parent | Enfant | Translation (m) | Source |
|---|---|---|---|
| `base_footprint` | `base_link` | `(0 ; 0 ; 0,076)` | `/tf_static` |
| `base_link` | `imu_link` | `(0,001 ; 0,017 ; 0,0322)` | `/tf_static` |
| `base_link` | `camera_link` | `(−0,0436 ; 0 ; 0,4196)` | `/tf_static` |
| `base_link` | `laser_link` | `(0,10478 ; 0 ; 0,0471)` | `/tf_static` |
| `arm_link4` | `mono_link` | `(−0,0481 ; −0,05145 ; −0,0022)` | `/tf_static` |

Chaîne du bras : `base_link` → `arm_link1` … `arm_link5` → `grip_joint` (pince), plus les parallélogrammes `rlink1-3` et `llink1-3`. Les quatre roues sont en joints continus `front_left_joint`, `front_right_joint`, `back_left_joint`, `back_right_joint`.

## 3. Articulations du bras

| Joint | Type | Axe | Limites (rad) |
|---|---|---|---|
| `arm_joint1` à `arm_joint4` | revolute | `0 0 -1` | `−1,5708` / `1,5708` |
| `arm_joint5` | revolute | `0 0 1` | `−1,5708` / `3,14159` |
| `grip_joint` | revolute | `0 0 1` | `−1,54` / `0` |

Ces limites sont celles du modèle, pas celles des servomoteurs (`0–180°`, `0–270°` sur l'axe 5). Aucune correspondance n'est établie entre le zéro du modèle et le zéro mécanique : voir [[bras_6dof]].

## 4. Correction du lidar (2026-11-10)

Le lien `laser_link` utilisait `meshes/sensor/laser_link.STL`, dont la boîte englobante mesurée est **97,5 × 71,8 × 57,0 mm** (154 549 triangles) : un modèle de lidar triangulation, pas le TOF monté sur le robot. Le capteur réel est un **YDLIDAR TG30**, Ø 75,8 mm hors tout, hauteur 34,7 mm, plan de scan à 27,9 mm au-dessus de la face d'appui, masse 214 g (datasheet YDLIDAR TG30, DOC# 01.13.000007, §Installation and dimensions).

Remplacement par un cylindre primitif dans `clawbot_x3plus.urdf` :

```xml
<visual>
  <origin xyz="0 0 -0.01055" rpy="0 0 0" />
  <geometry><cylinder radius="0.0379" length="0.0347" /></geometry>
</visual>
```

`laser_link` reste sur le plan de scan (`laser_joint` à `z = 0,0471` de `base_link`), donc le corps s'étend de `−27,9 mm` à `+6,8 mm` autour de l'origine du lien ; l'inertie est recalculée pour un cylindre de 214 g (`ixx = iyy = 9,832e-05`, `izz = 1,537e-04`).

Vérification : URDF revalidé (0 erreur), `clawbot-description.service` redémarré, `/robot_description` contient bien `cylinder radius="0.0379"` (2 occurrences : visuel et collision), et la transformation `base_link` → `laser_link` est inchangée `(0,105 ; 0 ; 0,047)`. Le maillage `laser_link.STL` n'est plus référencé par ce fichier ; il reste sur disque pour les autres variantes (`clawbot_X3.urdf`).

## 5. Anomalie connue : deux éditeurs de `/joint_states`

`joint_state_publisher` publie 15 articulations à zéro et `driver_node` publie 6 articulations de roues : deux éditeurs, deux jeux de noms. Conséquence : les angles du bras dans RViz sont des valeurs par défaut, pas des mesures. Le lanceur documente le compromis (« à retirer le jour où le pilote du bras publiera `/joint_states` ») ; la correction suppose que le pilote publie les angles lus sur le MCU, ce qui reste à faire ([[bras_6dof]] §3).

## 6. Vérification après modification

```bash
cd /home/jetson/clawbot
python3 urdf/validate_urdf.py urdf/clawbot_x3plus.urdf
sudo systemctl restart clawbot-description.service
export ROS_DOMAIN_ID=28 && source /opt/ros/humble/setup.bash
ros2 run tf2_ros tf2_echo base_link laser_link | head -6
ros2 param get /robot_state_publisher robot_description | grep -c 'cylinder radius="0.0379"'
```

## 7. Voir aussi

- Lidar décrit : [[ydlidar_tg30]]
- Caméra décrite : [[orbbec_astra_pro_plus]]
- Bras décrit : [[bras_6dof]]
- Publication des états d'articulation : [[yahboomcar_bringup_driver_node]]
- Service de description : [[systemd_robot_services]]
