---
title: "Bras — chaîne de commande, remise en service et pièges (état au 2026-11-11 19:25)"
date: "2026-11-11T18:00:00+01:00"
author: "Hermes Agent"
tags: [software, ros2, bras, servo, couple, diagnostic, validé]
status: validé
---

# Bras — chaîne de commande et remise en service

Cette page existe parce que la connaissance du bras était dispersée entre trois pages, un journal de
session et la mémoire de l'agent : à chaque reprise il fallait la reconstituer, et une conclusion
perdue se payait par un diagnostic refait. Elle rassemble **la chaîne**, **les faits mesurés** avec
leur date, **les pièges** et **ce qui reste ouvert**. Retour à l'[[index]] ; étalonnage et collisions :
[[etalonnage_bras]] ; matériel : [[bras_6dof]] ; précondition qui en dépend :
[[preconditions_mouvement]].

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
| 2026-11-11 17:35 | pilote **arrêté**, lecture directe `get_uart_servo_angle_array()` → `[76, 69, 90, 109, 110, 149]`, **exactement les consignes envoyées** | `scripts/read_arm_angles.py` |
| 2026-11-11 17:36:06 / 17:37:13 | `ros2-driver-node` puis `clawbot-arm-controller` redémarrés — **seul changement d'état** visible entre la panne et la reprise ; aucun test du bras entre 17:37 et 19:04 | `systemctl show -p ActiveEnterTimestamp`, journal |
| 2026-11-11 17:50 | test hors pile ROS : `set_uart_servo_torque(1)` puis servo 4 90°→95°, registre à jour | `scripts/test_couple_bras.py` |
| 2026-11-11 19:05 | servo 2 : 97 → 87 → 97, **le bras bouge** ; barycentre du masque sombre de la pince dans l'image frontale : 353,2 → 301,0 → 346,8 px, étendue au repos ±0,9 px | image Astra + `mesure_pince` |
| 2026-11-11 19:12 | consigne servo 4 20° → 40° : la relecture passe par **35°**, valeur **jamais commandée**, puis 39° | `/arm/servo_angles` échantillonné pendant le pas |
| 2026-11-11 19:14-19:20 | servo 4 de 90° à 0°, servo 3 de 90° à 0°, servo 1 de 76° à 90°, servo 2 de 97° à 180° : paliers de 10° acceptés et relus, `/safety/state` = `OK` | `/director/command` + journal arm-controller |
| 2026-11-11 19:15 | montée du servo 2 de 97° à 180° **sans contact** : segments `arm_link3`/`arm_link4` à x ≈ 0,015 m, mât à x ≈ −0,044 m | `scripts/cinematique_bras.py` |
| 2026-11-11 19:19 | la caméra du poignet regarde **vers l'avant**, dans le même sens que l'Astra : même scène dans les deux images (interrupteur du mur gauche, couloir au centre, portes sombres à droite) | captures comparées |
| 2026-11-11 19:20 | pose `[90, 180, 0, 0, 90, 149]` **validée par l'opérateur** comme repos et déplacement ; `arm_folded: true` après rechargement de l'enveloppe | opérateur + `/director/state` |

**Conclusion** : les servos exécutent les consignes, la chaîne fonctionne de bout en bout (directeur
→ contrôleur → `/servo_ctrl` → pilote → MCU → servos), et la relecture est redevenue une mesure. La
panne de 17:20 **n'est pas reproduite** ; elle a cessé après le redémarrage du pilote et du contrôleur
à 17:36-17:37, qui est le seul changement d'état visible entre les deux. La cause racine n'est **pas**
établie : un redémarrage qui efface le symptôme ne dit pas ce qui l'a produit.

## 3. Pose de repos et de déplacement

```text
servo 1   servo 2   servo 3   servo 4   servo 5   pince
   90       180         0         0        90        149
```

Validée par l'opérateur le 2026-11-11 à 19:20. Le bras est debout au-dessus de la colonne
(`arm_link3` et `arm_link4` à x ≈ 0,015 m, pince à x = 0,190 m / z = 0,304 m) et **la caméra du
poignet regarde vers l'avant**, dans le même sens que l'Astra : c'est la seule pose connue où le bras
est à la fois compact et utile à la perception pendant un déplacement. C'est elle que porte
`config/preconditions.yaml` depuis 19:24.

Les trois axes 2, 3 et 4 sont **sur leur butée** (`q = ±90°`, servo 0 ou 180). Une butée tenue par le
couple chauffe et bourdonne : un bruit continu au repos n'est pas normal.

## 4. Pièges (payés)

1. **`/arm/servo_angles` n'est pas toujours une mesure.** Quand les servos n'exécutent pas, le MCU
   renvoie son registre de consigne : le topic suit la consigne au degré près sur un bras immobile
   (constaté le 2026-11-11 à 17:35). Seule une valeur qui **diffère** de la consigne prouve que le
   servo travaille — c'est ce qu'on observe depuis 19:12. Ne jamais conclure « le bras a bougé » sur
   un relevé qui égale la consigne, ni « le bras est bloqué » sur un relevé qui la suit.
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
6. **Le seuil de collision du mât n'est pas une propriété du seul servo 2.** Le contact à ≈ 114° a été
   constaté le 2026-11-10 dans la configuration d'alors ; le 2026-11-11 à 19:15, avec `q3 = q4 = −90°`,
   la montée de 97° à 180° s'est faite sans contact. Le seuil dépend de q3 et q4 : le citer sans la
   pose qui l'accompagne induit en erreur.
7. **La cinématique directe ne dit pas où regarde la caméra du poignet.** Dans la pose validée,
   `scripts/cinematique_bras.py` annonce un axe optique à −90° (`wrist_camera_optical_frame`) alors
   que l'image montre l'horizon et la même scène que l'Astra. Le **cadre optique de l'URDF est mal
   orienté** ; il ne doit pas servir de référence d'orientation — voir [[camera_poignet]].
8. **Une image entièrement blanche n'est pas un défaut de netteté.** Le 2026-11-11, à `brightness=60`
   et `gain=70`, les 307 200 pixels de `/wrist_camera/image_raw` valaient 255. À `gain=0`,
   `brightness=0` : min 8, max 224, écart-type 61, image exploitable. Ce sont les réglages de départ de
   `clawbot-wrist-camera.service` qui saturent le capteur en scène proche et éclairée ; le module
   n'expose pas de temps d'exposition, le gain est le seul levier.

## 5. Ce qui est ouvert

| Point | Gravité | Détail |
|---|---|---|
| Cause de la panne du 17:20 non établie | moyen | le symptôme a disparu après redémarrage du pilote (17:36:06) et du contrôleur (17:37:13) ; un redémarrage qui efface ne dit pas ce qui a produit la panne. À instrumenter si elle revient |
| `DROP_TORQUE` n'actionne rien | **sécurité** | l'état est publié, le contrôleur s'arrête, mais aucun étage ne coupe le couple (`set_uart_servo_torque`). Décision prise, non appliquée |
| Réglages de gain de la caméra du poignet | moyen | `gain:=70` dans l'unité sature l'image ; la valeur correcte en lumière faible n'est pas mesurée |
| Cadre optique de l'URDF | moyen | orientation fausse (annonce −90° pour un axe horizontal) ; non corrigée, le fait mesuré fait foi |
| Encombrement de la pose de repos | moyen | validée par l'opérateur, pas mesurée au mètre ; seule la géométrie du mât sert de référence |

## 6. Protocole d'essai (à garder)

Paliers de 5 à 10°, relecture après chaque pas, jamais une trajectoire complète. `install/setup.bash`
est **obligatoire** : sans lui, `clawbot_interfaces` est introuvable et le script meurt sur
`ImportError: cannot import name 'DirectorCommand'`.

```bash
export ROS_DOMAIN_ID=28
source /opt/ros/humble/setup.bash && source /home/jetson/clawbot/install/setup.bash
python3 /home/jetson/clawbot/scripts/pas_bras.py --servo 2 --vers 170 --max-pas 10
```

Deux vérifications indépendantes, parce que la relecture seule ne suffit pas :

- **la relecture** : une valeur intermédiaire non commandée prouve le mouvement ; une valeur égale à
  la consigne ne prouve rien ;
- **l'image frontale** : le barycentre du masque sombre de la pince, stable à ±1 px au repos, se
  déplace de dizaines de pixels pour 10° sur le servo 2 ou 4.

Un palier de 10° est trop court pour que la relecture entrelacée (un servo par 600 ms) attrape une
valeur intermédiaire : l'absence de valeur intermédiaire sur un petit pas n'est pas une preuve de
blocage. Pour ce critère, faire un pas de 20°.

Dans tous les cas : maintenir l'alimentation à portée de coupure, pince vide, dégagement mesuré
autour du bras.

## 7. Voir aussi

- [[index]]
- [[etalonnage_bras]]
- [[bras_6dof]]
- [[preconditions_mouvement]]
- [[camera_poignet]]
- [[ERR-2026-11-10-007_retour_angle_servo_bras]]
- [[manipulation_moveit]]
