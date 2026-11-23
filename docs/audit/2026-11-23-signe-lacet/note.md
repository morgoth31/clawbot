# Note d'arbitrage — signe du lacet (2026-11-23)

| Champ | Valeur |
|---|---|
| Question | `wz(IMU)` et `wz(roues)` corrèlent à −0,983 : lequel est inversé par rapport à REP-103 ? |
| Exigence | REQ-DRV-018 (procédure `tests/hardware/HW-DRV-002.md`) |
| Mesures | hors robot, domaine 98/99, bag `slam2d_piece` du 2026-11-23, lecture seule |
| Statut | **clos le 2026-11-23 à 11:52** par l'essai `HW-DRV-002` : aucun capteur n'est inversé (voir §7) |

## 1. Ce qui est établi par la mesure

Séries appariées sur l'horodatage le plus proche, 3 009 paires sur 298 s :

| Corrélation | Valeur |
|---|---|
| `wz(lidar)` — `wz(roues)` | **+0,958** |
| `wz(lidar)` — `wz(IMU)` | **−0,953** |
| `wz(IMU)` — `wz(roues)` | **−0,991** (confirme le −0,983 du handoff) |

Sur les **206 paires de rotation franche** (|wz| > 0,10 rad/s et contraste d'appariement
> 0,05) :

| | IMU | roues |
|---|---|---|
| signe identique au lidar | **1,0 %** | **98,5 %** |
| pente lidar → capteur | **−0,997** | **+1,010** |
| intégrale sur la fenêtre | +9,6° | −11,2° (lidar : −7,7°) |

Une pente de −0,997 avec 1 % d'accord de signe, ce n'est pas un gain faux : c'est le **même
signal, signe inversé**.

**Origine matérielle écartée par la mesure** : la quantification de `angular_velocity.z` est
exactement 0,001 rad/s, ce qui identifie la trame **ICM20948** de `Rosmaster_Lib`. La branche
MPU9250 de cette bibliothèque nie `gy` et `gz` (`__parse_data`) ; ce n'est donc pas elle qui
produit l'inversion. La trame ICM transmet les trois axes sans négation : le signe vient du
capteur et de son montage, pas d'une correction de la bibliothèque.

## 2. L'hypothèse qui reste ouverte

Tout ce qui précède compare trois séries **entre elles**. La question « lequel est faux par
rapport à REP-103 » n'a de sens que si l'une des trois est une référence de sens connue. Le
lidar joue ce rôle — à une condition qu'il faut vérifier : **que `/scan` ne soit pas un
miroir**.

Le pilote applique, dans `CYdLidar.cpp` (YDLidar-SDK) :

```cpp
if (m_Reversion) angle = angle + M_PI;          // reversion: true
if (m_Inverted)  angle = 2*M_PI - angle;        // inverted:  true
```

soit `angle_sortie = 2π − (angle_brut + π)`. Cette formule est un **miroir composé d'une
rotation** : selon que le capteur balaie dans un sens ou dans l'autre, la sortie est fidèle
(à une rotation de π près) ou retournée gauche-droite. Rien dans le YAML ni dans le code ne
permet de savoir lequel des deux cas s'applique.

Mesure faite pour trancher partiellement — en avance pure, un déplacement `d` du capteur
donne `Δr(φ) ≈ −d·cos φ` dans un repère fidèle, et `+d·cos φ` dans un repère retourné d'un
demi-tour :

| Test | Paires | Résultat |
|---|---|---|
| avance pure (`|vx| > 0,08`, `|wz| < 0,06`) | 235 | pente `k = −8,97 mm/pair` pour un déplacement de 19,5 mm → **pas de miroir selon y** |
| déplacement latéral (`|vy| > 0,08`) | **0** | impossible : ce bag ne contient aucun strafe (`|vy| max = 0,022 m/s`) |

Le terme en `cos φ` est pair : il est **aveugle au miroir gauche-droite** (`φ → −φ`), qui est
précisément celui qui inverserait le sens de rotation. Ce miroir-là n'est donc **pas tranché**
par le bag, et aucun autre signal enregistré ne peut le trancher (le magnétomètre n'est pas
dans le bag, et sa convention vient de la même carte que le gyroscope).

## 3. Les deux mondes possibles, et ce qui les sépare

| Si `/scan` est… | alors `wz(IMU)` | alors `wz(roues)` | correctif |
|---|---|---|---|
| fidèle (sens REP-103) | **inversé** | correct | négation de `gz` à la publication dans le pilote ; l'EKF reste tel quel |
| miroir gauche-droite | correct | **inversé** | retour des roues, plus un défaut de sens du lidar à instruire pour le SLAM |

Une seule rotation d'un quart de tour dans un sens annoncé sépare ces deux lignes.
C'est l'objet de `tests/hardware/HW-DRV-002.md`, et les deux conclusions y sont écrites
d'avance pour que l'essai ne puisse pas être interprété après coup.

## 4. Indice indépendant (non démonstratif)

Si le miroir du lidar et l'inversion de l'IMU étaient **tous deux** présents, la prédiction de
l'EKF et l'évidence du scan se tromperaient du même côté : `slam_toolbox` produirait une carte
auto-cohérente (le monde vu en miroir) **sans murs dédoublés**. La carte réelle du 23/11
dédouble ses murs : c'est la signature d'une prédiction qui **contredit** le scan. Cet indice
pointe vers « IMU inversé, `/scan` fidèle », mais il dépend de la capacité de Ceres à suivre
ou non — il ne remplace pas la mesure.

## 5. Ce qui n'a pas été fait, volontairement

- **Aucune correction de code.** Retourner le mauvais capteur transforme une dérive de cap en
  emballement, et le symptôme devient plus difficile à lire qu'avant.
- **Aucune écriture dans le domaine 28** : ces mesures lisent un bag sur disque.
- Les outils livrés (`scripts/arbitrage_lacet.py`, `scripts/polarite_scan.py`) sont en lecture
  seule et rejouent n'importe quel bag contenant `/scan`, `/odom_raw`, `/imu/data_raw`.

## 6. Reproduction

```bash
export ROS_DOMAIN_ID=98
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME && source /opt/ros/humble/setup.bash
BAG=/var/lib/clawbot/test_data/slam2d_piece/slam2d_piece_0.db3
/usr/bin/python3 scripts/arbitrage_lacet.py "$BAG" /tmp/lacet.csv
/usr/bin/python3 scripts/polarite_scan.py "$BAG"
```

## 7. Résultat de l'essai physique — 2026-11-23 11:52

Deux passes, robot au sol, `clawbot-slam` arrêtée : deux rotations annoncées (anti-horaire puis
horaire), puis un **déplacement libre de 60 s** à la demande de l'opérateur, analysé contre le
lidar (584 paires de scans, 165 en rotation franche).

| Série | corrélation au lidar | pente | signes communs | intégrale |
|---|---|---|---|---|
| `wz(IMU)` | −0,980 | **−1,004** | 3,0 % | −152,0° |
| `wz(roues)` | +0,985 | +1,005 | 95,2 % | +158,1° |
| `wz` EKF (`/odom`) | +0,981 | **+1,004** | **98,2 %** | +152,2° |
| lidar | — | — | — | +143,0° |

**Conclusion : il n'y a pas de capteur inversé, et l'EKF a raison.** L'explication tient dans
la TF déployée `base_link → imu_link` : translation `[0.001, 0.017, 0.032]`, rotation
`RPY(-180.000°, 0.005°, -90.006°)`, dont la colonne z vaut `-1`. L'axe `+z` de `base_link`
sort en `-z` dans `imu_link` : une rotation anti-horaire **doit** y produire un `wz` négatif.
L'accéléromètre le confirme au repos (`z = −9,979 m/s²`).

`robot_localization` applique cette rotation avant de fusionner : la vitesse angulaire arrive
en `base_link` avec le bon signe, et la sortie le prouve (pente +1,004, 98,2 % de signes
communs, +95,3° intégrés pour un quart de tour physique).

Le **−0,983 de la passation comparait donc deux repères différents**. Le contournement de
REQ-DRV-011 ne masquait aucun défaut vivant, et corriger le signe à la publication aurait
fabriqué le défaut qu'on croyait corriger.

**Conséquence pour la carte :** la dérive de pose du 23/11 n'a pas cette cause. Elle reste à
trouver — glissement des roues en rotation, covariances, appariement — et l'A/B de
`docs/audit/2026-11-23-ab-slam/` a seulement montré que densifier le graphe divise par deux le
bruit d'appariement. Le prochain pas utile est de comparer, en rejeu, la cap de l'EKF à la cap
déduite du lidar sur tout le parcours : un écart qui se creuse en virage désignerait la
prédiction, un écart constant désignerait l'appariement.
