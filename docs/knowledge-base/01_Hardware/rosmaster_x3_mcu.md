---
title: "Carte Rosmaster X3 — lien série MCU / Jetson"
date: "2026-11-10T06:12:30+08:00"
author: "Hermes Agent"
tags: [hardware, mcu, rosmaster, uart, udev, serial, ch340, stm32, protocole]
status: validé
---

# Carte Rosmaster X3 — lien série MCU / Jetson

Interface de commande bas niveau du châssis Clawbot X3. Retour à l'[[index]] ; logiciel associé : [[yahboomcar_bringup_driver_node]] ; référence constructeur : [[documentation_constructeur_yahboom]].

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

Second pont USB-série du poste :

| Élément | Valeur |
|---|---|
| Périphérique | `/dev/ttyUSB0` |
| Identité | `Silicon_Labs CP2102 USB to UART Bridge Controller` (`10c4:ea60`, série `0001`) |
| Usage constaté | Télémètre laser TG30 via `/dev/ydlidar` (voir [[ydlidar_tg30]]) |

Troisième interface série visible dans `lsusb` mais sans nœud TTY : `1a86:7522 QinHeng Electronics USB Serial` (bus 001, device 011), aucun pilote lié (`/dev/ttyUSB*` et `/dev/ttyACM*` absents) — usage non identifié, `Donnée non disponible — aucun nœud /dev associé`.

## 2. Carte d'extension Rosmaster V3.0 — inventaire matériel

Référence : `04.Hardware course/1. About expansion board/1.About expansion boardV3.0.pdf` du dépôt `YahboomTechnology/ROSMASTERX3-PLUS`.

| Connecteur / composant | Fonction documentée |
|---|---|
| Entrée T DC 12 V | alimentation principale de la carte (batterie ou bloc 12 V) |
| Sorties DC 12 V (×2) | alimentation d'accessoires |
| Micro-USB | données vers l'hôte et programmation du microcontrôleur (pont CH340) |
| Type-C | alimentation 5,1 V / 5 A pour Raspberry Pi 5, sans données |
| Sortie DC 5 V | alimentation du Jetson |
| I2C | périphériques externes (écran OLED) |
| CAN | équipements CAN |
| SBUS | récepteur de radiocommande |
| Bandeau RGB | ruban adressable |
| Servos PWM ×4 | servos 5 V ou 6,8 V, sélection par cavalier |
| Port servo bus | servomoteurs série (bras) |
| Buzzer | signal sonore |
| Ports moteurs ×4 | moteurs M1 à M4 |
| SWD | débogage / flashage ST-Link ou J-Link |
| KEY1, RESET, BOOT0 | bouton utilisateur, réinitialisation, mode programmation |
| Centrale inertielle | ICM20948 en SPI2 (`SDA/SDI` PB15, `SCL` PB13, `AD0` PB14, `NSS` PB12) |

Périphériques pilotés par le microcontrôleur (même source, FAQ §1.3) : bras, buzzer actif, centrale inertielle, servos PWM, moteurs, ruban RGB, bouton KEY1, RESET, SBUS, CAN. Le Jetson ne dialogue avec aucun d'eux directement : tout passe par la trame série du §3.

Écarts V1.0 → V3.0 documentés : centrale inertielle ICM20948 (au lieu de MPU9250), ajout du SWD et d'une entrée interrupteur externe, protocole d'alimentation Raspberry Pi 5, révision de circuit ; **la version V3.0 exige la bibliothèque Python 3.3.x ou supérieure**. La bibliothèque installée ici est 3.3.1, ce qui est cohérent avec une carte V3.0 — la sérigraphie de la carte n'a pas été relevée.

Correspondance moteurs / encodeurs (source : `12.Control motor` et `13.Timer captures the encoder data`) :

| Moteur | Position | Driver | Timer encodeur | PWM |
|---|---|---|---|---|
| M1 | avant gauche | AM2861 | TIM2 | TIM1 (PA8) |
| M2 | arrière gauche | AM2861 | TIM4 | TIM1 (PB0) |
| M3 | avant droit | AM2861 | TIM5 | TIM1 (PB1) |
| M4 | arrière droit | AM2861 | TIM3 | TIM1 (PA11) |

Vitesse moteur : `±(3600 − MOTOR_IGNORE_PULSE)`, zone morte filtrée côté firmware ; `set_motor()` travaille en PWM sans asservissement, `set_car_motion()` en boucle fermée sur les encodeurs (PID incrémental, cf. `15. PID control robot movement`).

## 3. Trame d'échange applicative

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

Période de publication fixée par `self.create_timer(0.1, self.pub_data)` dans `Mcnamu_driver_X3.py:69` ; les 10 Hz mesurés sur `/voltage` et `/imu/data_raw` confirment cette période. Cette période est celle du **nœud ROS 2**, pas celle du report MCU (voir §4).

## 4. Protocole série bas niveau

Spécification lue dans la bibliothèque réellement installée, `Rosmaster_Lib.py` (lignes 25-27, 257-287) :

| Octet | Émission Jetson → MCU | Réception MCU → Jetson |
|---|---|---|
| 0 | `0xFF` | `0xFF` |
| 1 | `0xFC` (identifiant de carte) | `0xFB` (`0xFC − 1`) |
| 2 | `LEN` = nombre d'octets suivant `LEN` (fonction + données + somme) | idem |
| 3 | `FUNC` (code fonction) | idem |
| 4… | données | données |
| dernier | somme = `(Σ octets 0..n-1 + 5) & 0xFF`, avec `5 = 257 − 0xFC` | somme = `(LEN + FUNC + données) & 0xFF` |

Le contrôle de réception ignore les deux octets d'en-tête et compare la somme partielle au dernier octet ; une trame dont la somme ne correspond pas est ignorée silencieusement (`check sum error` uniquement en mode `debug=True`).

Codes fonction reconnus par la bibliothèque :

| Code | Fonction | Sens |
|---|---|---|
| `0x01` | report automatique (`set_auto_report_state`) | → MCU |
| `0x02` | buzzer (`set_beep`) | → MCU |
| `0x03` / `0x04` | servo PWM / quatre servos PWM | → MCU |
| `0x05` / `0x06` | ruban RGB / effet RGB | → MCU |
| `0x0A` | vitesse (`vx`, `vy`, `vz` en mm/s) + tension batterie (V) | ← MCU |
| `0x0B` | centrale MPU9250 brute (9 × `int16`) | ← MCU |
| `0x0E` | centrale ICM20948 brute (9 × `int16`, facteur 1/1000) | ← MCU |
| `0x0C` | angles d'attitude (`int16` / 10 000) | ← MCU |
| `0x0D` | encodeurs des quatre roues (4 × `int32`) | ← MCU |
| `0x0F` | réinitialisation d'état | → MCU |
| `0x10` / `0x11` / `0x12` | moteurs en PWM / déplacement simple / consigne de vitesse | → MCU |
| `0x13` / `0x14` | PID moteur / PID de lacet | → MCU |
| `0x15` | type de châssis | → MCU |
| `0x20` / `0x21` / `0x22` | servo bus (angle) / identifiant / couple | → MCU |
| `0x23` / `0x24` | bras (6 angles) / décalage de zéro | → MCU |
| `0x30` / `0x31` | angle par défaut / angle de braquage AKM | ↔ MCU |
| `0x50` | demande de données (`__request_data`) | → MCU |
| `0x51` | version du firmware MCU | ← MCU |
| `0xA0` | effacement de la Flash (retour usine) | → MCU |

Cadence de report automatique : `set_auto_report_state(True)` fait émettre **quatre trames différentes toutes les 10 ms**, donc chaque trame est rafraîchie toutes les 40 ms (documentation de l'API dans `05.Basic course/3. Install the Rosmaster driver library`). Le nœud ROS 2 échantillonne ce cache toutes les 100 ms : une valeur ne peut donc pas être plus fraîche que 40 ms, et la période de 100 ms constatée sur les topics est un choix du nœud, pas une limite du MCU.

Trame capturée : le 2026-11-10 à 11:43 CET, `ros2-driver-node.service` arrêté 1,2 s, `Rosmaster_Lib` ouvert sur `/dev/myserial` et instrumentation de `__parse_data`. Sur 1,2 s : `0x0A` ×30, `0x0C` ×31, `0x0D` ×31, `0x0E` ×30, soit 100 trames/s (10 ms par trame) et 25 Hz par type, donc 40 ms de rafraîchissement par grandeur. Le service a été redémarré immédiatement après et `/voltage` republie à 10 Hz.

| Grandeur lue à cette capture | Valeur |
|---|---|
| Version du firmware MCU (`get_version()`, aussi publiée sur `/edition`) | `3.5` |
| PID de déplacement (`get_motion_pid()`) | `kp = 0,8` / `ki = 0,06` / `kd = 0,5` |
| Type de châssis lu sur la carte (`get_car_type_from_machine()`) | `1` (X3 mecanum) |
| Attitude fusionnée (`get_imu_attitude_data()`) | roll `0,418°`, pitch `0,458°`, yaw `−5,460°` |
| Accéléromètre / gyroscope | `(−0,073 ; 0,048 ; −9,871)`, `(0,01 ; 0,005 ; 0,005)` |
| Magnétomètre | `(−15,9 ; −18,749 ; −12,736)` |
| Encodeurs M1–M4 (robot immobile) | `0, 0, 0, 0` |
| Tension | `11,9 V` |

L'attitude de la trame `0x0C` est désormais convertie en quaternion dans `/imu/data_raw` (voir [[yahboomcar_bringup_driver_node]]) ; auparavant le nœud publiait l'identité `(0, 0, 0, 1)` en ignorant cette trame.

## 5. Bus CAN

| Élément | Valeur | Source |
|---|---|---|
| Interface `can0` | État `DOWN`, aucune adresse | `ip -brief addr` |
| Trafic constaté | Aucun (interface non montée) | `ip -brief addr` |
| Utilisation par la chaîne ROS 2 | Donnée non disponible — aucun nœud du domaine 28 ne publie sur un topic CAN | `ros2 topic list` |

La carte expose un connecteur CAN et le microcontrôleur le gère (cours `7. CAN bus communication`), mais aucun équipement CAN n'est câblé sur ce robot.

## 6. Paramètres du nœud client

| Paramètre | Valeur par défaut | Source |
|---|---|---|
| `car_type` | `X3` | `Mcnamu_driver_X3.py:34` |
| `imu_link` | `imu_link` | `Mcnamu_driver_X3.py:37` |
| `Prefix` | chaîne vide | `Mcnamu_driver_X3.py:40` |
| `xlinear_limit` | 1,0 | `Mcnamu_driver_X3.py:43` |
| `ylinear_limit` | 1,0 | `Mcnamu_driver_X3.py:46` |
| `angular_limit` | 5,0 | `Mcnamu_driver_X3.py:49` |

## 7. Firmware du microcontrôleur

| Élément | Valeur | Source |
|---|---|---|
| Version du firmware | `3.5` | `get_version()` sur `/dev/myserial`, 2026-11-10 11:43 CET ; publiée aussi sur `/edition` (`3.5`) |
| PID de déplacement en mémoire | `0,8 / 0,06 / 0,5` | `get_motion_pid()` |
| Type de châssis en mémoire | `1` (X3) | `get_car_type_from_machine()` |
| Fichier de firmware constructeur | `Rosmaster_XXX.hex` fourni avec les cours `05.Basic course/1. Update the firmware` | dépôt constructeur |
| Procédure de mise à jour | non exécutée sur ce robot | [[mise_a_jour_firmware_carte_rosmaster]] |

La version 3.5 est cohérente avec une carte V3.0 et une bibliothèque 3.3.1 (exigence constructeur : ≥ 3.3.x pour la V3.0). Aucun test de persistance Flash n'a été réalisé : écrire avec `forever=True` puis couper l'alimentation reste à faire, `Donnée non disponible`.

## 8. Voir aussi

- Nœud ROS 2 qui pilote ce lien : [[yahboomcar_bringup_driver_node]]
- Télémètre laser sur le second pont série : [[ydlidar_tg30]]
- Énergie mesurée via ce lien : [[batterie_principale]]
- Unité systemd associée : [[systemd_robot_services]]
- Dépôt constructeur et cours matériels : [[documentation_constructeur_yahboom]]
- Procédure de flashage du MCU : [[mise_a_jour_firmware_carte_rosmaster]]
