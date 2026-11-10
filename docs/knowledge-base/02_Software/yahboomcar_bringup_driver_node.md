---
title: "yahboomcar_bringup — nœud de conduite Mcnamu_driver_X3"
date: "2026-11-10T06:13:38+08:00"
author: "Hermes Agent"
tags: [software, ros2, driver, yahboomcar, cmd_vel, mecanum, imu]
status: validé
---

# `yahboomcar_bringup` — nœud de conduite `Mcnamu_driver_X3`

Nœud `/driver_node`, unique interface entre le graphe ROS 2 et la carte Rosmaster. Retour à l'[[index]] ; matériel associé : [[rosmaster_x3_mcu]].

## 1. Déploiement

| Élément | Valeur | Source |
|---|---|---|
| Exécutable | `ros2 run yahboomcar_bringup Mcnamu_driver_X3` | `systemctl cat ros2-driver-node.service` |
| Unité systemd | `ros2-driver-node.service` (actif, `Restart=on-failure`, `RestartSec=5`) | `systemctl list-units` |
| Dépendance | `Requires=ros2-hardware-service.service` | `systemctl cat ros2-driver-node.service` |
| Répertoire de travail | `/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws` | `systemctl cat ros2-driver-node.service` |
| Espace de travail sourcé | `/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash` | `systemctl cat ros2-driver-node.service` |
| Source du nœud | `/home/jetson/clawbot/yahboomcar_bringup/yahboomcar_bringup/Mcnamu_driver_X3.py` | Système de fichiers |
| Bibliothèque matérielle | `Rosmaster_Lib` 3.3.1 | `py_install_V3.3.1/Rosmaster_Lib/` |

## 2. Abonnements

| Topic | Type | Callback | Source |
|---|---|---|---|
| `/cmd_vel` | `geometry_msgs/msg/Twist` | `cmd_vel_callback` | `Mcnamu_driver_X3.py:58` |
| `/RGBLight` | `std_msgs/msg/Int32` | `RGBLightcallback` | `Mcnamu_driver_X3.py:59` |
| `/Buzzer` | `std_msgs/msg/Bool` | `Buzzercallback` | `Mcnamu_driver_X3.py:60` |
| `/servo_ctrl` | `std_msgs/msg/Int32MultiArray` | `Servocallback` | `Mcnamu_driver_X3.py:61` |

## 3. Publications

| Topic | Type | Période | Source |
|---|---|---|---|
| `/voltage` | `std_msgs/msg/Float32` | 100 ms | `Mcnamu_driver_X3.py:62,69` |
| `/edition` | `std_msgs/msg/Float32` | 100 ms | `Mcnamu_driver_X3.py:63,69` |
| `/joint_states` | `sensor_msgs/msg/JointState` | 100 ms | `Mcnamu_driver_X3.py:64,69` |
| `/vel_raw` | `geometry_msgs/msg/Twist` | 100 ms | `Mcnamu_driver_X3.py:65,69` |
| `/imu/data_raw` | `sensor_msgs/msg/Imu` | 100 ms | `Mcnamu_driver_X3.py:66,69` |
| `/imu/mag` | `sensor_msgs/msg/MagneticField` | 100 ms | `Mcnamu_driver_X3.py:67,69` |

Cadences mesurées sur le graphe : `/voltage` = 10,000 Hz ; `/imu/data_raw` = 9,999 Hz (conformes à la période de 100 ms du timer).

## 4. Paramètres déclarés

| Paramètre | Valeur par défaut | Source |
|---|---|---|
| `car_type` | `X3` | `Mcnamu_driver_X3.py:34` |
| `imu_link` | `imu_link` | `Mcnamu_driver_X3.py:37` |
| `Prefix` | chaîne vide | `Mcnamu_driver_X3.py:40` |
| `xlinear_limit` | 1,0 | `Mcnamu_driver_X3.py:43` |
| `ylinear_limit` | 1,0 | `Mcnamu_driver_X3.py:46` |
| `angular_limit` | 5,0 | `Mcnamu_driver_X3.py:49` |

## 5. État des données de conduite à la capture

| Grandeur | Valeur | Source | Horodatage |
|---|---|---|---|
| `/vel_raw` linéaire x | 0,000 m/s | `ros2 topic echo --once /vel_raw` | 2026-11-10 06:12:58 CST |
| `/vel_raw` angulaire z | 0,000 rad/s | idem | idem |
| `/imu/data_raw` accélération | x = −0,011 ; y = −0,028 ; z = −9,852 m/s² | `ros2 topic echo --once --field linear_acceleration` | 2026-11-10 06:13:20 CST |
| `/imu/data_raw` orientation | quaternion issu de l'attitude MCU : `x = 0,00377 ; y = 0,00352 ; z = −0,04769 ; w = 0,99885`, soit un lacet de `−5,47°` | `ros2 topic echo --once` | 2026-11-10 12:02 CET |
| `/imu/data_raw` vitesse angulaire x | 0,003 rad/s | idem | idem |
| `/imu/data_raw` `frame_id` | `imu_link` | idem | idem |
| `/cmd_vel` | Aucun message reçu en 12 s (timeout) ; 2 éditeurs déclarés, 1 abonné | `ros2 topic info /cmd_vel` | 2026-11-10 06:14:10 CST |
| `/joint_states` | Publié à 10 Hz par ce nœud (6 articulations de roues) et par `joint_state_publisher` (15 articulations à zéro) | `ros2 topic echo --once /joint_states` | 2026-11-10 11:26 CET |

**Correction du 2026-11-10 (acquisition IMU).** Le nœud publiait l'identité `(0, 0, 0, 1)` alors que la carte envoie l'attitude fusionnée dans la trame `0x0C` : la fonction `get_imu_attitude_data()` était ignorée. `pub_data()` convertit désormais roll/pitch/yaw en quaternion (`Mcnamu_driver_X3.py:164-176`). Reconstruit sans édition incrémentale (`rm -rf build install`, `colcon build`), service redémarré, vérifié sur `/imu/data_raw` : lacet `−5,47°` contre `−5,460°` lus directement sur la carte. Les covariances restent à `0` : aucun étalonnage de bruit n'a été fait, `0` signifiant « inconnu » (REP-145).

## 6. Voir aussi

- Graphe complet : [[ros2_graph_clawbot]]
- Lien série et udev : [[rosmaster_x3_mcu]]
- Tension publiée par ce nœud : [[batterie_principale]]
