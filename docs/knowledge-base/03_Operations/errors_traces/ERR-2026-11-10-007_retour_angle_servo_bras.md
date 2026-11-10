---
title: "ERR-2026-11-10-007 — retour d'angle invalide du servo 4 du bras"
date: "2026-11-10T11:58:00+01:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, bras, servo, bus-serie, rosmaster]
status: ouvert
---

# ERR-2026-11-10-007 — retour d'angle invalide du servo 4 du bras

| Champ | Valeur |
|---|---|
| Identifiant | `ERR-2026-11-10-007` |
| Horodatage de détection | 2026-11-10T11:44:00+01:00 (CET) |
| Domaine ROS 2 | 28 |
| Topics concernés | Aucun — la lecture se fait sur le lien série `/dev/myserial`, hors ROS |
| Composant lié | [[bras_6dof]], [[rosmaster_x3_mcu]] |
| Gravité d'exploitation | Contrôle du bras en position, pas de blocage du châssis |
| Statut | ouvert — contourné dans la pile de manipulation |
| Mitigation appliquée | Articulation `arm_joint4` déclarée **passive** dans `clawbot_arm_controller` : sa position est publiée dans `/arm/joint_states` mais aucune consigne n'est envoyée au servo 4 (voir §3) |

## 1. Nature de l'échec

`get_uart_servo_angle_array()` renvoie un angle négatif pour le servo 4 alors que la conversion de la bibliothèque produit une valeur comprise entre 0 et 180°. Deux appels consécutifs donnent `−5` puis `−1`, cette dernière valeur signifiant « lecture invalide » dans `Rosmaster_Lib`. Les servos 1, 2, 3, 5 et 6 renvoient des valeurs stables identiques d'un appel à l'autre.

## 2. Preuves

`ros2-driver-node.service` arrêté, bibliothèque `py_install_V3.3.1` utilisée directement :

```
$ python3 -c "... Rosmaster().get_uart_servo_angle_array() ..."
[71, 155, 54, -5, 90, 149]
[71, 155, 54, -1, 90, 149]
```

Les deux appels ont lieu à moins d'une seconde d'intervalle, robot immobile, alimentation sur batterie à `11,9 V`, version de firmware MCU `3.5`.

Chaîne de conversion concernée (`Rosmaster_Lib.py:290-320`) : impulsion `s_value` → `s_angle = (s_value − 900) × (0 − 180) / (3100 − 900) + 180`. Une impulsion lue sous `900` produit un angle négatif, ce qui est exactement le signe observé.

## 3. Actions de mitigation

| Horodatage | Action | Résultat mesuré |
|---|---|---|
| 2026-11-10T11:44:00+01:00 | Consignation ; aucun réglage de zéro ni écriture Flash | Aucune modification ; deux lectures reproductibles |
| 2026-11-10T11:44:05+01:00 | Redémarrage de `ros2-driver-node.service` | Service actif, `/voltage` à 10 Hz |
| 2026-11-10T22:41:00+01:00 | Nouvelle lecture avant essais physiques (3 appels, pilote arrêté) | `[71, 156, 55, -5, 90, 149]` trois fois de suite : le servo 4 renvoie toujours `-5` |
| 2026-11-10T22:48:00+01:00 | Trajectoire MoveIt exécutée sur l'axe 1 avec `passive_joints: [arm_joint4]` | servo 4 relu à `-5` avant et après : aucune consigne ne lui a été envoyée, aucun saut |
| 2026-11-10T22:54:00+01:00 | `scripts/sync_arm_pose.py` | détecte l'angle invalide, écrit `initial_positions[3] = 0.0` et ajoute l'articulation à `passive_joints` automatiquement |

## 4. Conditions de clôture

1. Trois appels consécutifs à `get_uart_servo_angle(4)` renvoient une valeur dans `0–180`.
2. `get_uart_servo_angle_array()` renvoie six valeurs positives, identiques à 2° près sur trois appels.
3. Si la lecture reste invalide après réglage du zéro (`set_uart_servo_offset(4)`), remplacement du servo et nouvelle consignation de la valeur.

## 5. Voir aussi

- Description du bras et des six servos : [[bras_6dof]]
- Lien série et protocole : [[rosmaster_x3_mcu]]
- Modèle géométrique : [[modele_urdf_clawbot]]
