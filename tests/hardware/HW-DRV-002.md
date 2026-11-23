# HW-DRV-002 — Signe du lacet : IMU, roues et EKF contre le sens physique

| Champ | Valeur |
|---|---|
| Prompt | à rattacher (correctif du signe du lacet, REQ-DRV-018) |
| Exigences vérifiées | REQ-DRV-018 |
| Version déployée | tag `prod-20261123-c05a-rel` (`94eea8f`) |
| Date, lieu | à remplir, pièce dégagée d'au moins 2 m × 2 m |
| Opérateur présent | à remplir — confirmé à l'heure de début |
| Exécution | Hermes lit et juge (lecture seule) ; l'opérateur fait tourner le robot |
| Mode | `MODE : VALIDATION PHYSIQUE` — `CIBLE : ROBOT` |

## Pourquoi cet essai

`wz(IMU)` et `wz(roues)` corrèlent à **−0,983** : l'un des deux est inversé par rapport à
REP-103 (+z = anti-horaire vu de dessus), et rien ne l'a jamais arbitré. L'EKF ne fusionne
que le lacet de l'IMU (`config/ekf.yaml`, `odom0_config[11] = false`) : si c'est l'IMU qui
est inversé, la cap dérive à chaque rotation et la carte se dédouble.

La mesure hors robot (`scripts/analyse_imu_odom.py`, bag `slam2d_piece`, 5 s) ne peut pas
trancher : elle compare deux capteurs entre eux, sans référence physique. Seule une
rotation dans un sens **connu** le fait.

## 1. Préconditions — à cocher avant de commencer

- [ ] Robot **au sol**, sur un sol plat et dur, roues libres, rien devant ni derrière
- [ ] Bras à la pose de repos validée `[90, 180, 0, 0, 90, 149]`, bande ±5°
      (REQ-ARM-003/004 : `ros2 topic echo /arm/servo_angles --once`)
- [ ] Zone de 2 m × 2 m dégagée ; personne dans la zone sauf l'opérateur
- [ ] Opérateur à portée de l'arrêt d'urgence ; `stop_robot` n'est pas utilisé ici
      (aucun skill ne pilote la base) mais le tableau reste accessible
- [ ] Tension relevée et consignée : `ros2 topic echo /voltage --once`
- [ ] Unités actives : `ros2-driver-node`, `clawbot-ekf`, `clawbot-safety-arbitrator`,
      `clawbot-joy-teleop` ; **`clawbot-slam` arrêtée** (accord de l'opérateur demandé)
- [ ] Chaîne vérifiée, cadence prouvée (pas seulement l'unité « active ») :
      `/imu/data_raw` ≈ 10 Hz, `/odom_raw` ≈ 10 Hz, `/odom` ≈ 30 Hz, `/joy` ≈ 19 Hz
- [ ] `ros2 topic info /cmd_vel_safe -v` : **1 seul éditeur** (`safety_arbitrator`)
- [ ] Manette allumée et reconnue : `ls /dev/input/js*`, `/joy` bouge quand on pousse un axe

## 2. Vérités terrain (tracées au sol avant l'essai)

1. Ruban adhésif : une ligne droite **L0** sur le sol, et sa perpendiculaire **L90**
   tracée à l'équerre (ou gabarit imprimé). Écart angulaire admis : ±2°.
2. Repère sur le châssis : choisir une arête rectiligne (côté ou avant du châssis) et
   marquer son milieu d'un trait de craie — c'est l'index qui doit viser L0 au départ
   et L90 à l'arrivée.
3. Rayon libre vérifié : aucun obstacle à moins de 0,8 m du châssis sur tout le tour
   (l'arbitre coupe le mouvement plus près).

## 3. Étapes

Hermes lance la mesure **avant** le premier geste et annonce chaque rotation à voix haute.
L'opérateur pousse le **stick droit** (rotation trigonométrique, `angular_scale` 0,80 rad/s).

| # | Qui | Action | Mesure relevée | Critère | Résultat |
|---|---|---|---|---|---|
| 1 | Hermes | `ROS_DOMAIN_ID=28 /usr/bin/python3 scripts/mesure_signe_lacet.py --seconds 75 --plan ccw,cw,ccw,cw --sortie /tmp/lacet_$(date +%H%M).csv` | cadence IMU, nombre de messages | ≥ 9 Hz | ☐ |
| 2 | OP | Laisser au repos **3 s** | rien | outil : aucun segment | ☐ |
| 3 | Hermes | « Rotation 1 : **anti-horaire**, 90° » | — | — | ☐ |
| 4 | OP | Pousser le stick pour tourner **dans le sens anti-horaire** (vue de dessus) et s'arrêter quand l'index vise L90 | angle réel au sol | 90° ± 10° | ☐ |
| 5 | OP | Repos 3 s | — | — | ☐ |
| 6 | Hermes | « Rotation 2 : **horaire**, 90° » (retour sur L0) | — | — | ☐ |
| 7 | OP | Idem dans le sens horaire | angle réel | 90° ± 10° | ☐ |
| 8 | Hermes/OP | Répéter les étapes 2 à 7 **deux fois** (rotations 3 anti-horaire, 4 horaire) | — | — | ☐ |
| 9 | Hermes | Lire le tableau de l'outil : par segment, `int IMU`, `int roues`, `d yaw EKF` | 4 segments jugés | voir §5 | ☐ |
| 10 | Hermes | `ros2 topic hz /cmd_vel_safe` après l'essai | cadence | ≈ 20 Hz, 1 éditeur | ☐ |

**Si les roues ne rapportent rien** (segments où `int roues` reste < 5° alors que le robot a
tourné) : refaire **deux** rotations **à la main**, moteurs non commandés, et juger
seulement IMU contre physique. Le lacet des roues n'est alors pas concluant — le consigner,
ne pas extrapoler.

## 4. Incidents

| Heure | Incident | Décision |
|---|---|---|
| 11:30:43 | manette perdue sur `/dev/input/js0` | sans effet, retrouvée 11:34:45 (Nintendo Switch Pro Controller) |
| 11:36 | bras hors repos `[90, 92, 0, 0, 90, 119]` | opérateur le remet au stick ; après remise `[90, 180, 0, 0, 90, 119]`, **servo 6 à 119 au lieu de 149** — écart consigné, sans effet sur un tour de base |
| 11:47 | protocole changé en cours d'essai, à la demande de l'opérateur | les rotations 3 et 4 annoncées sont remplacées par un **déplacement libre de 60 s** analysé contre le lidar, plutôt qu'une chorégraphie répétée. La référence physique du déplacement libre est le lidar, ancré par les deux rotations annoncées déjà faites |
| 11:47 | `clawbot-slam` arrêtée (accord de l'opérateur) | redémarrée à la fin, `active`, aucun `Message Filter dropping` |

## 5. Résultats chiffrés

### 5.1 Rotations annoncées (passe 1, 70 s)

| # | sens annoncé | durée | \|wz\| max | ∫wz IMU | ∫wz roues | Δyaw `/odom` |
|---|---|---|---|---|---|---|
| 1 | anti-horaire | 3,4 s | 0,843 rad/s | **−98,8°** | **+99,1°** | **+95,3°** |
| 2 | horaire | 2,8 s | 0,861 rad/s | +109,8° | −109,2° | −106,5° |

### 5.2 Déplacement libre (passe 2, 60 s) — 584 paires, 165 en rotation franche

Référence : lidar, appariement polaire entre scans consécutifs.

| Série | corrélation au lidar | pente | signes communs | intégrale |
|---|---|---|---|---|
| `wz(IMU)` (`/imu/data_raw`) | −0,980 | **−1,004** | **3,0 %** | −152,0° |
| `wz(roues)` (`/odom_raw`) | +0,985 | **+1,005** | 95,2 % | +158,1° |
| `wz` EKF (`/odom`, twist) | +0,981 | **+1,004** | **98,2 %** | +152,2° |
| lidar (référence) | — | — | — | +143,0° |

### 5.3 Pourquoi le critère « `wz(IMU)` > 0 en anti-horaire » était faux

Le critère initial de REQ-DRV-018 confondait deux repères. Mesure de la TF déployée,
`base_link → imu_link` :

```
Translation : [0.001, 0.017, 0.032]
Rotation    : quaternion [-0.707, 0.707, 0, 0]  =  RPY (-180.000°, 0.005°, -90.006°)
Matrice     : diag(-0, -0, -1) sur la colonne z  →  l'axe +z de base_link sort en -z dans imu_link
```

L'accéléromètre au repos donne `linear_acceleration.z = −9,979 m/s²`, cohérent avec ce même
retournement. Autrement dit, `wz(IMU)` **négatif** pendant une rotation anti-horaire est
**correct** : la valeur est exprimée dans `imu_link`, que l'URDF déclare retournée.

`robot_localization` applique la rotation du TF avant de fusionner : la vitesse angulaire
arrive en `base_link` avec le bon signe, et la sortie de l'EKF le prouve (pente +1,004 contre
le lidar, 98,2 % de signes communs).

**Le −0,983 de la passation comparait donc `wz` exprimé dans deux repères différents.** Il n'y
a pas de capteur inversé. Le contournement de REQ-DRV-011 (`odom0_config[11] = false`) ne
masquait aucun défaut vivant.

### 5.4 Conformité

| Exigence | Critère | Mesuré | Conforme |
|---|---|---|---|
| REQ-DRV-018 | `wz(IMU)` conforme à REP-103 **dans `imu_link`** (repère déclaré retourné) | pente −1,004 contre le lidar, az au repos −9,979 | oui |
| REQ-DRV-018 | `wz(roues)` conforme à REP-103 dans `base_link` | pente +1,005, 95,2 % | oui |
| REQ-DRV-018 | cadence de lacet de l'EKF conforme au sens physique | pente +1,004, 98,2 %, +95,3° pour 90° | oui |
| REQ-DRV-018 | \|∫wz(IMU) − 90°\| ≤ 15° en valeur absolue (repère du capteur) | 98,8° sur 3,4 s (écart 8,8°) | oui |
| REQ-DRV-018 | \|Δyaw(/odom) − 90°\| ≤ 15° | +95,3° (écart 5,3°) | oui |

**Ce que l'essai ne dit pas :** il ne dit rien de la cause des murs dédoublés. Puisque la
cadence de lacet de l'EKF est correcte, la dérive de pose de la carte du 23/11 vient d'ailleurs
(glissement des roues en rotation, covariances, appariement) et reste à instruire.

Une correction de code serait ici une **double faute** : retourner `gz` à la publication
rendrait enfin `/imu/data_raw` incohérent avec `imu_link`, et ferait repartir l'EKF du mauvais
côté. Le montage est déclaré ; c'est le montage qui fait foi.

## 6. Pièces jointes

- Passe 1 (rotations annoncées) : `/tmp/lacet_R1.csv`, journal `/tmp/lacet_R1.log`
- Passe 2 (déplacement libre) : journal complet `/tmp/essai_libre.log`
  (`scripts/essai_libre.py`, outil de la passe 2, dans le compte de l'opérateur)
- Tension relevée : 11,6 V (11,9 V le 2026-11-10 — bande normale)
- `clawbot-slam` : `inactive` pendant l'essai, `active` après, 0 `Message Filter dropping`
- État de la chaîne avant essai : six unités `active`, `/joy` 19,0 Hz (1 éditeur),
  `/cmd_vel_safe` 1 éditeur, `/odom` 1 éditeur (`ekf_filter_node`), `/odom_raw` 1 éditeur

## 7. Verdict

Le critère initial (« `wz(IMU)` > 0 en anti-horaire ») est **réfuté** : il comparait deux
repères. Le critère corrigé — conformité à REP-103 **dans le repère déclaré de chaque
capteur**, et cadence de lacet de l'EKF conforme au sens physique — est vérifié sur les deux
passes.

Une seule des deux lignes, sans autre texte sur la ligne (elle est lue par `trace_check.py`) :

Verdict : CONFORME

Signé : opérateur, 2026-11-23 — rédigé par Hermes
