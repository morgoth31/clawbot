---
title: "Bras — chaîne de commande, remise en service et pièges (état au 2026-11-11 18:00)"
date: "2026-11-11T18:00:00+01:00"
author: "Hermes Agent"
tags: [software, ros2, bras, servo, couple, diagnostic, open]
status: ouvert
---

# Bras — chaîne de commande et remise en service

Cette page existe parce que la connaissance du bras était dispersée entre trois pages, un journal de
session et la mémoire de l'agent : à chaque reprise il fallait la reconstituer, et une conclusion
perdue se payait par un diagnostic refait. Elle rassemble **la chaîne**, **les faits mesurés** avec
leur date, **les pièges** et **ce qui reste ouvert**. Retour à l'[[index]] ; étalonnage et collisions :
[[etalonnage_bras]] ; matériel : [[bras_6dof]].

## 1. Chaîne de commande, de bout en bout

```text
contrôleur de bras            pilote (copie constructeur)            carte
arm_trajectory_server  --1--> Servocallback                -->  MCU  --> servos 1..6
  FollowJointTrajectory        [servo_id, angle_deg]                (couple global)
  /servo_ctrl (Int32MultiArray)(set_uart_servo_angle)                    |
        |                                                                |
        +---- /arm/joint_states (consigne, 20 Hz)                        |
                                                                         v
        /arm/servo_angles (10 Hz, 1 servo par tick, cycle ~600 ms) <----+
```

| Élément | Fait | Source |
|---|---|---|
| Le pilote active le couple au démarrage | `set_uart_servo_torque(True)` ligne 102 | `Mcnamu_driver_X3.py` (trois copies identiques : `src/`, `install/`, dépôt) |
| Format attendu par le pilote | `data[0]` = id servo (1-6), `data[1]` = angle en degrés | `Servocallback`, ligne 140 |
| Une commande par servo et par période | `/servo_ctrl` porte **une** paire, pas un tableau de six | idem |
| Le pilote ne commande que les axes qui changent | journal : « 1 consignes servo » vs « 5 consignes servo » | `clawbot-arm-controller` |
| Correspondance articulation → servo | `servo = 90 + 57,2958 × q`, bornes 0-180° (0-270° servo 5) | `config/arm_controller.yaml` |
| Pince | `servo 6 = 180 + 116,88 × q`, `q ∈ [-1,54 ; 0]` | idem |

## 2. Faits mesurés, avec leur date

| Date | Fait | Preuve |
|---|---|---|
| 2026-11-10 23:45 | servo 2 consigné 120°, **relu 114°** puis contact du mât : la relecture **retardait** sur la consigne quand le servo forçait | [[etalonnage_bras]] §5.2 |
| 2026-11-10 23:38 | servo 4 remis en service par rebranchement ; `q4` balayé de 0 à 180° sans collision une fois l'objet retiré | [[ERR-2026-11-10-007_retour_angle_servo_bras]] |
| 2026-11-11 12:45 | pose supposée au démarrage du contrôleur : `[-0,244, +0,122, 0, 0, 0]`, pince `-0,265` | journal `clawbot-arm-controller` |
| 2026-11-11 17:20 | consigne `arm_move` acceptée, « trajectoire terminée, 5 consignes servo », **le bras ne bouge pas** (constat opérateur) | journal + opérateur |
| 2026-11-11 17:23-17:25 | axes 2 puis 4 commandés par paliers de 7 à 10°, registre à jour à chaque pas, **aucun mouvement** | journal + opérateur |
| 2026-11-11 17:35 | pilote **arrêté**, lecture directe `Rosmaster_Lib.get_uart_servo_angle_array()` → `[76, 69, 90, 109, 110, 149]`, **exactement les consignes envoyées** | `scripts/read_arm_angles.py` |
| 2026-11-11 17:50 | test hors pile ROS : `set_uart_servo_torque(1)` puis servo 4 90°→95°, registre à jour | `scripts/test_couple_bras.py` |

**Conclusion à ne pas dépasser** : le MCU répond (version 3.5, 11,90 V), il **enregistre** les
consignes, et il les **renvoie** à la lecture. Cette relecture ne prouve donc pas une position.
Le 2026-11-10, quand un servo forçait, la valeur relue différait de la consigne : la lecture était
alors une mesure. Elle ne l'est plus aujourd'hui, ce qui est en soi le symptôme à expliquer.

## 3. Pièges (payés)

1. **`/arm/servo_angles` n'est pas une preuve de position.** Un pas « effectué » à l'identique de la
   consigne ne démontre rien. Seule une lecture qui **diffère** de la consigne prouve que le servo
   travaille. Ne jamais conclure « le bras a bougé » sur un registre qui suit la consigne.
2. **Un `systemctl stop ros2-driver-node` met la pile en cascade** : `Requires=` entraîne l'arrêt de
   l'arbitre, du contrôleur de bras, du directeur, du sentinel et de Nav2. Relancer le seul pilote
   laisse six unités en `failed` — et l'agent croit ensuite que « tout tourne ». Après toute
   manipulation du port série : `systemctl list-units --state=failed` puis relance dans l'ordre
   `driver → ekf → arbitre → description → bras → directeur → caméra → nav2 → sentinel → yolo`.
3. **Le port série est exclusif** : aucune lecture directe (`Rosmaster_Lib`) pendant que
   `ros2-driver-node` tourne, sinon les trames se volent et le pilote redémarre en boucle.
4. **Les réglages caméra sont volatils** : `brightness`/`gain` posés par `ros2 param set` disparaissent
   au redémarrage du service — les mettre dans l'unité (fait le 2026-11-11 17:58).
5. **Deux lecteurs peuvent ouvrir `/dev/video0` sans erreur** et se voler les tampons : le second
   meurt sur `Failed mapping device memory`. Un seul propriétaire, les autres lisent le topic.

## 4. Ce qui est ouvert

| Point | Gravité | Détail |
|---|---|---|
| Les servos n'exécutent pas les consignes | **bloquant** | depuis le 2026-11-11 17:20 ; le registre suit, le bras ne bouge pas, l'alimentation et la carte sont saines. Causes possibles : couple refusé par le MCU, chaîne de bus servo interrompue (daisy chain), mode servo différent |
| La relecture ne mesure plus | **moyen** | conséquence directe du point ci-dessus ; toute la supervision du bras en dépend |
| `DROP_TORQUE` n'actionne rien | sécurité | `set_uart_servo_torque` existe et le pilote l'appelle au démarrage, mais aucun étage ne le rappelle sur l'état `DROP_TORQUE` |

### Protocole du test qui départage (opérateur présent, 1 minute)

```bash
export ROS_DOMAIN_ID=28 && source /opt/ros/humble/setup.bash
python3 /home/jetson/clawbot/scripts/pas_bras.py --servo 2 --vers 87 --max-pas 12   # 10°
```

| Observation | Conclusion |
|---|---|
| le bras bouge de ~10° | la chaîne fonctionne ; le défaut est dans la pile ROS (à reprendre côté contrôleur) |
| rien ne bouge, bras **raide** | couple actif mais consignes non exécutées : voir le mode servo / la chaîne de bus |
| rien ne bouge, bras **mou** | couple absent : la commande `set_uart_servo_torque` n'atteint pas les servos |
| la relecture **retarde** sur la consigne | le servo répond : la lecture redevient une mesure |

Dans tous les cas : maintenir l'alimentation à portée de coupure, pince vide, dégagement mesuré
autour du bras.

## 5. Voir aussi

- [[index]]
- [[etalonnage_bras]]
- [[bras_6dof]]
- [[ERR-2026-11-10-007_retour_angle_servo_bras]]
- [[manipulation_moveit]]
- [[preconditions_mouvement]]
