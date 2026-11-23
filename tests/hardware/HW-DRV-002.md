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

<tableau à remplir : arrêt de l'arbitre, refus de mouvement, dérapage, heure, décision>

## 5. Résultats chiffrés

| Exigence | Critère | Mesuré | Conforme |
|---|---|---|---|
| REQ-DRV-018 | `wz(IMU)` > 0 sur **chaque** rotation anti-horaire | à remplir | oui / non |
| REQ-DRV-018 | `wz(roues)` > 0 sur chaque rotation anti-horaire | à remplir | oui / non |
| REQ-DRV-018 | \|∫wz(IMU) − 90°\| ≤ 15° par rotation | à remplir | oui / non |
| REQ-DRV-018 | \|Δyaw(/odom) − 90°\| ≤ 15° par rotation | à remplir | oui / non |
| REQ-DRV-018 | les deux capteurs s'accordent en signe sur les 4 rotations | à remplir | oui / non |

**Décision attendue, sans ambiguïté :**

- IMU négatif en anti-horaire, roues positives → **l'IMU est inversé** ; le correctif est
  dans le pilote (négation de `gz` à la publication ou à la source), pas dans l'EKF.
- IMU positif, roues négatives → **le retour des roues est inversé** ; corriger
  `feedback()`/`twist.angular.z` du pilote, et vérifier que `odom0_config[11]` reste à
  `false` (la fusion ne doit pas dépendre de ce retour).
- Les deux positifs → le désaccord de signe n'est pas reproduit à cette cadence ; relancer
  la corrélation sur le bag de l'essai avant de conclure quoi que ce soit sur la carte.
- Les deux négatifs → le sens physique annoncé est faux ou le repère de montage est
  retourné : ne rien corriger, refaire l'essai avec la marque au sol et l'équerre.

**Ne pas corriger « au passage » un seul côté sans avoir rempli les quatre rotations** :
corriger le mauvais capteur transforme une dérive en emballement.

## 6. Pièces jointes

- CSV de l'outil : `/tmp/lacet_HHMM.csv`
- Sortie complète de l'outil (tableau des 4 segments)
- `ros2 topic hz` avant/après pour `/imu/data_raw`, `/odom_raw`, `/odom`, `/cmd_vel_safe`
- Tension relevée, heure de début et de fin

## 7. Verdict

Une seule des deux lignes, sans autre texte sur la ligne (elle est lue par `trace_check.py`) :

Verdict : CONFORME
Verdict : NON CONFORME

Signé : <opérateur>, <date> — rédigé par Hermes
