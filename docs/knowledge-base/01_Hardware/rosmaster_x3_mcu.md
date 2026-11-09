---
title: "Carte Rosmaster X3 — lien série MCU / Jetson"
date: "2026-11-10T06:12:30+08:00"
author: "Hermes Agent"
tags: [hardware, mcu, rosmaster, uart, udev, serial, ch340]
status: validé
---

# Carte Rosmaster X3 — lien série MCU / Jetson

Interface de commande bas niveau du châssis Clawbot X3. Retour à l'[[index]] ; logiciel associé : [[yahboomcar_bringup_driver_node]].

## 1. Chemin matériel

| Élément | Valeur | Source |
|---|---|---|
| Pont USB-série déclaré | `1a86:7523 QinHeng Electronics CH340 serial converter` | `lsusb` |
| Périphérique TTY | `/dev/ttyUSB1` | `udevadm info -q property -n /dev/ttyUSB1` |
| Nom stable udev | `/dev/myserial` → `ttyUSB1` (lien symbolique) | `ls -l /dev/myserial` |
| Règle udev | `KERNEL=="ttyUSB*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE:="0777", SYMLINK+="myserial"` | `/etc/udev/rules.d/serial.rules:1` |
| Débit série | 115 200 Bd | `Rosmaster_Lib.py:20` (`serial.Serial(com, 115200)`) |
| Bibliothèque cliente | `Rosmaster_Lib` 3.3.1 (`py_install_V3.3.1`) | `/home/jetson/yahboomcar_ros2_ws/software/py_install_V3.3.1/Rosmaster_Lib/` |
| Type de châssis configuré | `X3` (mecanum), `set_car_type(1)` | `Mcnamu_driver_X3.py:32-35` |

Second pont USB-série présent, non utilisé par la conduite :

| Élément | Valeur |
|---|---|
| Périphérique | `/dev/ttyUSB0` |
| Identité | `Silicon_Labs CP2102 USB to UART Bridge Controller` (`10c4:ea60`, série `0001`) |
| Usage constaté | Aucun nœud ROS 2 ne l'ouvre (voir [[ros2_graph_clawbot]]) |

## 2. Trame d'échange applicative

| Sens | Topic ROS 2 | Type | Période |
|---|---|---|---|
| Jetson → MCU | `/cmd_vel` | `geometry_msgs/msg/Twist` | Événementiel |
| Jetson → MCU | `/RGBLight` | `std_msgs/msg/Int32` | Événementiel |
| Jetson → MCU | `/Buzzer` | `std_msgs/msg/Bool` | Événementiel |
| Jetson → MCU | `/servo_ctrl` | `std_msgs/msg/Int32MultiArray` | Événementiel |
| MCU → Jetson | `/imu/data_raw` | `sensor_msgs/msg/Imu` | 100 ms (10 Hz mesuré) |
| MCU → Jetson | `/imu/mag` | `sensor_msgs/msg/MagneticField` | 100 ms |
| MCU → Jetson | `/vel_raw` | `geometry_msgs/msg/Twist` | 100 ms |
| MCU → Jetson | `/voltage` | `std_msgs/msg/Float32` | 100 ms (10 Hz mesuré) |
| MCU → Jetson | `/joint_states` | `sensor_msgs/msg/JointState` | 100 ms |

Période de publication fixée par `self.create_timer(0.1, self.pub_data)` dans `Mcnamu_driver_X3.py:69` ; les 10 Hz mesurés sur `/voltage` et `/imu/data_raw` confirment cette période.

## 3. Bus CAN

| Élément | Valeur | Source |
|---|---|---|
| Interface `can0` | État `DOWN`, aucune adresse | `ip -brief addr` |
| Trafic constaté | Aucun (interface non montée) | `ip -brief addr` |
| Utilisation par la chaîne ROS 2 | Donnée non disponible — aucun nœud du domaine 28 ne publie sur un topic CAN | `ros2 topic list` |

## 4. Paramètres du nœud client

| Paramètre | Valeur par défaut | Source |
|---|---|---|
| `car_type` | `X3` | `Mcnamu_driver_X3.py:34` |
| `imu_link` | `imu_link` | `Mcnamu_driver_X3.py:37` |
| `Prefix` | chaîne vide | `Mcnamu_driver_X3.py:40` |
| `xlinear_limit` | 1,0 | `Mcnamu_driver_X3.py:43` |
| `ylinear_limit` | 1,0 | `Mcnamu_driver_X3.py:46` |
| `angular_limit` | 5,0 | `Mcnamu_driver_X3.py:49` |

## 5. Voir aussi

- Nœud ROS 2 qui pilote ce lien : [[yahboomcar_bringup_driver_node]]
- Énergie mesurée via ce lien : [[batterie_principale]]
- Unité systemd associée : [[systemd_robot_services]]
