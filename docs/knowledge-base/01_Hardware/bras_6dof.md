---
title: "Bras robotique 6 axes — servomoteurs bus série"
date: "2026-11-10T11:54:00+01:00"
author: "Hermes Agent"
tags: [hardware, bras, arm, servo, bus-serie, mcu, urdf, joint_states]
status: actif
---

# Bras robotique 6 axes — servomoteurs bus série

Bras monté sur le châssis, commandé par la carte Rosmaster ([[rosmaster_x3_mcu]]) via son port « serial servo ». Présence physique confirmée par l'utilisateur le 2026-11-10 ; description géométrique : [[modele_urdf_clawbot]].

## 1. Constitution

| Élément | Valeur | Source |
|---|---|---|
| Degrés de liberté | 5 axes + pince (6 servomoteurs) | description `clawbot_x3plus.urdf` : `arm_joint1` à `arm_joint5`, `grip_joint` |
| Type de servo | bus série (UART), identifiants `1` à `6` | `Rosmaster_Lib.py:989-1062`, `docs` constructeur `04.Hardware course/10. Control serial port servos` |
| Port carte | « serial servo interface » de la carte d'extension | `04.Hardware course/1. About expansion boardV3.0` |
| Couple | activé par le nœud de conduite à l'initialisation (`set_uart_servo_torque(True)`) | `Mcnamu_driver_X3.py:76` |
| Course logicielle | `0–180°` pour les servos 1 à 4 et 6 ; `0–270°` pour le servo 5 | conversion angle → impulsion de `Rosmaster_Lib.py:290-310` |
| Impulsions | servos 1–4 et 6 : `900–3100` ; servo 5 : `380–3700` | idem |

Le bras n'est pas piloté par un nœud ROS dédié : `/servo_ctrl` (`std_msgs/msg/Int32MultiArray`, `[id, angle]`) est converti par `Mcnamu_driver_X3.py` en `set_uart_servo_angle(id, angle)` pour `id` de 1 à 6, puis envoyé au MCU. Aucun retour de position n'est publié sur un topic.

## 2. Lecture réelle des angles

Capture du 2026-11-10 à 11:44 CET, `ros2-driver-node.service` arrêté une seconde, `get_uart_servo_angle_array()` :

```
[71, 155, 54, -5, 90, 149]      # appel 1
[71, 155, 54, -1, 90, 149]      # appel 2, servo 4 non lu
```

| Servo | Angle lu (appel 1) | Angle lu (appel 2) | Interprétation |
|---|---|---|---|
| 1 | 71° | 71° | stable |
| 2 | 155° | 155° | stable |
| 3 | 54° | 54° | stable |
| 4 | −5° | −1° (`-1` = lecture invalide) | **instable**, voir [[ERR-2026-11-10-007_retour_angle_servo_bras]] |
| 5 | 90° | 90° | stable |
| 6 | 149° | 149° | stable |

Les valeurs sont les angles renvoyés par la carte, pas la position géométrique du modèle URDF : le zéro mécanique de chaque servo n'est pas identifié.

## 3. Ce que le système publie réellement

| Topic | Éditeur | Contenu constaté |
|---|---|---|
| `/joint_states` | `joint_state_publisher` (lancement `clawbot-description.service`) | 15 articulations à `0,0` : `arm_joint1`…`arm_joint5`, `grip_joint`, `rlink_joint2-3`, `llink_joint1-3`, quatre roues |
| `/joint_states` | `driver_node` | 6 articulations de roues seulement (`back_right_joint`, `back_left_joint`, `front_left_steer_joint`, `front_left_wheel_joint`, `front_right_steer_joint`, `front_right_wheel_joint`) |

Deux éditeurs sur le même topic avec des jeux de noms différents : les angles du bras affichés dans RViz sont des **zéros de confort**, pas des mesures. Toute utilisation d'un filtre ou d'une cinématique doit savoir que la position du bras n'est pas acquise par le système.

## 4. Limites constatées

- Aucune acquisition ROS de la position du bras : le MCU la connaît (voir §2), le nœud ne la publie pas.
- Servo 4 : retour d'angle négatif ou invalide, `Donnée non disponible` pour une position fiable.
- Aucun zéro mécanique documenté par axe ; la correspondance `angle servo` → `angle URDF` n'est pas établie.
- Aucun essai de charge (masse maximale en bout de bras) n'a été réalisé, `Donnée non disponible`.

## 5. Voir aussi

- Carte qui pilote le bras : [[rosmaster_x3_mcu]]
- Nœud qui traduit `/servo_ctrl` : [[yahboomcar_bringup_driver_node]]
- Modèle géométrique et TF : [[modele_urdf_clawbot]]
- Trace du défaut de lecture du servo 4 : [[ERR-2026-11-10-007_retour_angle_servo_bras]]
- Cours constructeur du bras : [[documentation_constructeur_yahboom]]
