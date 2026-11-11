---
title: "ERR-2026-11-11-010 — Base non proportionnelle : temps mort, saturation et signe inversé"
date: "2026-11-11T08:40:00+01:00"
author: "Hermes Agent"
tags: [erreur, base-mobile, mcu, err-009, odometrie, mecanum, pid]
status: ouvert
---

# ERR-2026-11-11-010 — Base non proportionnelle

**Sévérité** : bloquante pour l'odométrie, Nav2, le suivi de personne et toute tâche de déplacement.
**Composant** : carte Rosmaster X3 **Plus** (STM32 + CH340, firmware 3.5), bibliothèque
`Rosmaster_Lib` 3.3.9, driver `Mcnamu_driver_X3.py`.
**Rattachement** : ERR-009 (commande de vitesse et `/odom` non fiables), confirmée et précisée ici.

## 1. Symptômes mesurés le 2026-11-11

### 1.1 Roues libres, sur cales — signe

Séquence de quatre échelons de 2 s, valeurs moyennes du retour `/vel_raw` sur la seconde moitié :

| Consigne (m/s) | Retour brut | Après correction |
|---|---|---|
| +0,020 | 0,000 | 0,001 |
| +0,050 | **−0,843** | +0,737 |
| +0,100 | **−1,259** | +1,262 |
| −0,050 | **+0,745** | −0,790 |

Conclusion ferme : **le MCU renvoie la vitesse avec le signe inversé**, sur les trois amplitudes.
La correction est appliquée au retour (`feedback()` dans `cmd_scaling.py`), pas à la consigne.

### 1.2 Roues au sol, sous charge

Consigne **+0,05 m/s** pendant 4 s, robot face à un mur à 2,38 m :

- vitesse mesurée nulle pendant **~1,2 s** (temps mort), puis saut à **0,28 m/s** en un échantillon ;
- moyenne sur la seconde moitié : **0,082 m/s** → gain apparent **1,64** ;
- pic à **5,6 ×** la consigne ;
- déplacement réel confirmé par lidar : le mur passe de 237,8 cm à 231,6 cm, soit ~6 cm d'avance,
  alors que `/odom` annonçait un recul — cohérent avec le signe inversé, corrigé depuis.

La sonde a coupé d'elle-même à 1,6 s sur son garde-fou de survitesse. Aucun dégât.

### 1.3 Un échelon antérieur, au sol, avant correction du signe

Consigne +0,06 m/s : mouvement après 1,2 s, saut à −0,20 m/s (signe faux), arrêt par la sonde à
1,5 s, 10 cm parcourus. Le comportement est reproductible.

## 2. Ce qui est établi

1. **Le signe du retour est inversé par le MCU** — mesuré sur cales, trois amplitudes, deux signes.
2. **Le temps mort est d'environ 1,2 s** avant tout mouvement, à toutes les amplitudes testées.
3. **La réponse est fortement non linéaire** : 0,05 m/s donne 0,74 sur cales et 0,082 sous charge ;
   0,10 donne 1,26 sur cales. La sortie plafonne vers **1,29** quelle que soit la consigne.
4. **La sortie de `/cmd_vel` est propre** : un seul écrivain pendant les essais, vitesse nulle
   publiée à l'arrêt, aucun mouvement résiduel (`/odom` stable à 0,0000 m sur 5 s).
5. **Le driver n'envoie pas le type de châssis** : il instancie `Rosmaster()` avec `car_type=1`
   par défaut et n'appelle jamais `set_car_type()`, alors que la trame `set_car_motion` embarque
   cet octet et que la documentation de la bibliothèque donne des plages différentes par modèle
   (X3 : ±1,0 m/s ; X3 Plus : ±0,7 m/s et ±3,2 rad/s).

## 3. Ce qui reste hypothétique

- **H1 — type de châssis faux dans la trame.** Le profil cinématique envoyé au MCU ne serait pas
  celui du X3 Plus. Explique un gain faux et une saturation précoce ; explique mal, à elle seule,
  un temps mort de 1,2 s. **Non vérifié** : `get_car_type_from_machine()` renvoie `-1` hors du
  driver, et le type réel n'a pas encore été lu depuis le processus du driver.
- **H2 — boucle de vitesse mal réglée (PID).** Un `Ki` élevé avec saturation pendant le temps mort
  produit exactement la séquence observée : rien pendant 1,2 s, puis emballement. **Non vérifié** :
  `get_motion_pid()` renvoie `[-1, -1, -1]` hors du driver.
- **H3 — phase A/B d'un encodeur inversée.** Une contre-réaction positive expliquerait l'emballement
  mieux que le gain. **Non vérifié** : l'inversion observée est globale (les trois amplitudes), ce
  qui plaide pour une convention de firmware plutôt que pour un câblage ; mais aucune roue n'a été
  testée individuellement à la main.

## 4. Ce qui a été corrigé en logiciel

| Correctif | Fichier | Effet | Vérifié |
|---|---|---|---|
| Signe du retour | `cmd_scaling.py::feedback()`, appliqué dans le driver | `/vel_raw` et `/odom_raw` dans la convention ROS | oui, sur cales |
| Bande morte et butées | `cmd_scaling.py::scale_cmd_vel()` | aucune consigne sous 2 % n'atteint le MCU, butée à 0,35 m/s | oui, tests |
| `/odom_raw` en `Odometry` | driver | l'EKF peut consommer le retour (un `Twist` nu est inutilisable) | oui, 10 Hz |
| Fusion EKF | `config/ekf.yaml`, `launch/ekf.launch.py` | `/odom` + TF `odom→base_link`, stables à l'arrêt | oui |

Ces correctifs rendent l'odométrie **lisible et de signe correct** ; ils ne rendent pas la base
proportionnelle. Un gain dans le driver masquerait la moyenne en laissant les pics.

## 5. Protocole de mesure pour trancher

Robot au sol, couloir de 3 m dégagé, sonde `scripts/base_probe_l1.py` (arrêt garanti, garde-fou
lidar 0,30 m, plancher de tension 10,8 V, coupure si survitesse 5 échantillons) :

| Tir | Consigne | Durée | Ce qu'il mesure |
|---|---|---|---|
| 1 | 0,02 m/s | 3 s | seuil mort réel |
| 2 | 0,05 m/s | 3 s | gain en bas de plage |
| 3 | 0,10 m/s | 3 s | linéarité |

Critère de sortie : les trois rapports mesuré/consigné dans ±10 %, temps mort < 200 ms.
Si les trois saturent ou partent en à-coup, la cause est en amont du driver.

## 6. Actions à mener

| # | Action | Côté | État |
|---|---|---|---|
| 1 | Journaliser `get_car_type_from_machine()` et `get_motion_pid()` au démarrage du driver | logiciel | **à faire** |
| 2 | Si le type lu n'est pas celui du X3 Plus, appeler `set_car_type()` driver arrêté (EEPROM, réversible) | carte | à faire |
| 3 | Relever le PID de vitesse et le comparer à un réglage sain ; ajuster via `set_motion_pid()` si `Ki` est manifestement excessif | carte | à faire |
| 4 | Faire tourner chaque roue à la main, roues libres, et vérifier le signe du compte encodeur roue par roue | **physique** | à faire |
| 5 | Vérifier la version de firmware avec l'outil Yahboom et appliquer un correctif s'il en existe un pour le X3 Plus | **firmware** | à faire |
| 6 | En dernier recours, asservissement de vitesse dans S1 (écrêtage des pics) | logiciel | non engagé |

## 7. Ce que l'opérateur doit fournir

- la valeur de `car_type` **réellement lue** sur la carte (test 2) ;
- la valeur du PID moteur (test 3) ;
- la documentation ou l'outil Yahboom de la carte, pour savoir si le X3 Plus attend un profil
  cinématique distinct et quel firmware le corrige ;
- le résultat du test roue par roue (test 4), pour distinguer convention globale et câblage.

## 8. Voir aussi

- [[inventaire_materiel]] — état du sous-système base
- [[rosmaster_x3_mcu]] — carte de commande
- [[manipulation_moveit]] — ce qui dépend d'une base fiable pour la saisie
- [[ERR-2026-11-10-009_commande_vitesse_non_proportionnelle]] — incident d'origine
- Conception S1/S2 : `docs/superpowers/specs/2026-11-11-architecture-s1-s2-design.md`
