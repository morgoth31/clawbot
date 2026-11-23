# A/B slam_toolbox — les paramètres denses de REQ-DRV-012 (rendu)

| Champ | Valeur |
|---|---|
| Date des mesures | 2026-11-23, 09:13 à 09:23 CET |
| Exigence concernée | REQ-DRV-012 |
| Statut de ce document | A/B rendu **après** la mise en production : il justifie a posteriori un réglage déjà déployé |
| Exécution | hors robot, domaine 99, rejeu d'un bag — aucune commande envoyée au robot |

## 1. Objet

Les réglages denses du SLAM (`minimum_time_interval 0.1`, `minimum_travel_distance 0.05`,
`minimum_travel_heading 0.05`, `correlation_search_space_dimension 0.8`) sont en production
dans `services/clawbot-slam.service` depuis `rel-C05a`, alors que l'A/B qui devait les
justifier n'avait **jamais été comparé** : les deux cartes existaient, personne n'en avait
tiré de chiffres. Ce document rend cet A/B.

## 2. Question, et critère de jugement fixé d'avance

**Le réglage dense réduit-il le bruit d'appariement sans perdre de couverture ?**

Le critère n'est ni la taille du fichier `.pgm` ni le nombre de cellules connues : la
couverture varie peu entre deux variantes et ne dit rien de la netteté. Le critère retenu
est le nombre de **cellules occupées isolées** — une cellule occupée sans aucun voisin occupé
dans son 3×3 n'est pas un mur, c'est un écho mal apparié. C'est le meilleur indicateur de
netteté disponible sur un `.pgm` de `map_server`
(`clawbot-dev-cycle/references/fusion-imu-odometrie.md`, § « Juger une carte par des chiffres »).

Mesures secondaires : surface du cadre (étalement de la dérive à parcours égal), cellules
connues et leur part (information perdue ou non).

## 3. Dispositif

- **Bag** : `/var/lib/clawbot/test_data/slam2d_piece` (298 s), rejoué en **domaine 99** avec
  `--clock -r 1.0`, topics `/scan /odom_raw /imu/data_raw /tf_static`.
- **EKF** : `config/ekf.yaml` **identique dans les deux variantes** — seul le jeu de
  paramètres `slam_toolbox` change. Conséquence à garder en tête : le défaut de signe du
  lacet (REQ-DRV-018) est présent dans les deux passes ; il accompagne la comparaison sans
  la fausser, puisque c'est le même EKF des deux côtés.
- **Variante A** (avant) : `minimum_time_interval 0.5`, `minimum_travel_distance 0.1`,
  `minimum_travel_heading 0.1`, `correlation_search_space_dimension 0.5`.
- **Variante B** (dense, REQ-DRV-012) : `0.1` / `0.05` / `0.05` / `0.8`.
- Communs : `resolution 0.05`, `min_laser_range 0.15`, `max_laser_range 8.0`,
  `map_update_interval 2.0`, shim TF `laser_link → laser` (le bag porte le cadre `laser`).
- **Sauvegarde de la carte à t+292 s**, pendant que le temps simulé tourne encore : après la
  fin du bag, `/clock` s'arrête, les nœuds gèlent et le `map_saver` rend `result=255`. Le
  `map_saver` interne de `slam_toolbox` échoue de toute façon en rejeu ; la carte est écrite
  par `scripts/sauve_carte.py` (abonnement `TRANSIENT_LOCAL`).
- **Passes** : A de 09:13:16 à 09:18:12, B de 09:18:36 à 09:23:33. Chacune a rejoué le bag
  entier ; `Using solver plugin` présent dans les deux journaux, une seule ligne
  `Message Filter dropping message` par passe (au démarrage, TF pas encore stabilisée).

Reproductible par :

```bash
export ROS_DOMAIN_ID=99
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME && source /opt/ros/humble/setup.bash
scripts/ab_slam_toolbox.sh A --out /tmp/ab_slam
scripts/ab_slam_toolbox.sh B --out /tmp/ab_slam
/usr/bin/python3 scripts/compare_cartes_ab.py /tmp/ab_slam/carte_A.pgm /tmp/ab_slam/carte_B.pgm
```

## 4. Résultats

| Métrique | A (0,5 s / 10 cm / 0,5 m) | B (0,1 s / 5 cm / 0,8 m) | Écart |
|---|---|---|---|
| cadre (cellules) | 160 × 217 | 160 × 205 | hauteur −5,5 % |
| surface théorique | 86,8 m² | 82,0 m² | **−4,8 m² (−5,5 %)** |
| cellules connues | 14 462 | 14 012 | −450 (−3,1 %) |
| part connue du cadre | 41,7 % | 42,7 % | +1,1 pt |
| cellules libres | 11 101 | 10 563 | −538 (−4,8 %) |
| cellules occupées | 3 361 | 3 449 | +88 (+2,6 %) |
| **cellules occupées isolées** | **108** | **47** | **−61 (−56,5 %)** |
| part des occupées qui sont isolées | 3,2 % | 1,4 % | −1,9 pt |

Contrôle de cohérence : ces comptes reproduisent exactement ceux écrits par le sauveur au
moment des passes (`save_A.log` : 160×217, connues 14 462 (41,7 %), occupées 3 361 ;
`save_B.log` : 160×205, connues 14 012 (42,7 %), occupées 3 449). Deux comptages
indépendants du même fichier donnent le même résultat.

## 5. Lecture

- **Le bruit d'appariement est divisé par deux** (108 → 47 cellules isolées, −56,5 %). C'est
  l'effet attendu du réglage dense : scans intégrés quatre fois plus souvent (0,1 s au lieu
  de 0,5 s sur un lidar à 10 Hz, où 0,5 s revenait à jeter quatre scans sur cinq), nœuds tous
  les 5 cm au lieu de 10, et une fenêtre de recherche de 0,8 m qui laisse Ceres rattraper une
  erreur de cap en virage.
- **Le cadre rétrécit de 5,5 %** à parcours identique : la trajectoire estimée s'étale moins.
- **Aucune information perdue** : la part connue du cadre est stable (41,7 % → 42,7 %) alors
  que le cadre est plus petit, donc la densité utile par mètre carré augmente.
- **Les murs ne sont pas plus nombreux, ils sont plus continus** : +2,6 % de cellules occupées
  avec −4,8 % de surface et −56 % d'isolées. Un mur en tirets compte moins de cellules qu'un
  mur continu ; l'augmentation va dans le sens de la continuité, pas du dédoublement.
- Rendu visuel : `ab_slam_2026-11-23.png`, avec A à gauche (contours fragmentés, points noirs
  dispersés) et B à droite (contours continus) — la figure est régénérée depuis les deux
  `.pgm` par `scripts/compare_cartes_figure.py`, ses libellés sont recalculés, pas recopiés.

**Conclusion pour REQ-DRV-012 : le réglage dense est justifié.** Sur le même bag, avec le
même EKF, il divise par deux le bruit d'appariement sans perdre de couverture et en réduisant
l'étalement de la trajectoire.

## 6. Ce que cet A/B ne prouve pas

1. **Ce n'est pas le robot.** Rejeu : pas de glissement de roue mécanum réel, pas de latence
   du MCU, pas de charge CPU du poste. Un réglage dense sur le robot coûte ce que le rejeu ne
   mesure pas — la référence donnait 3 % d'un cœur pour `minimum_time_interval` 0,5 → 0,1 s.
2. **Il ne corrige pas la carte du 23/11.** La carte réelle (183×189, murs dédoublés, éventail
   de rayons) porte la signature d'une **dérive de pose**, pas d'un manque de densité. Si le
   lacet de l'IMU est inversé (REQ-DRV-018), aucune densité de graphe ne rattrape une
   prédiction de cap qui part dans le mauvais sens à chaque rotation.
3. **Il ne dit rien du signe du lacet.** Le même `ekf.yaml` est utilisé des deux côtés : la
   comparaison est un différentiel sur les paramètres SLAM, elle ne peut pas arbitrer
   IMU contre roues.
4. **Une seule passe par variante.** L'écart (−56,5 %) est assez large pour ne pas dépendre
   du bruit d'une passe, mais ce n'est pas une série statistique. Si une variante C était
   envisagée (0,05 s ? `correlation_search_space_dimension` 1,0 ?), il faudrait trois passes
   par variante.

## 7. Artefacts

Conservés hors du dépôt, hors de `/tmp` (volatile) : `/home/jetson/clawbot_fonctions/mesures_ab/`

| Fichier | Taille | md5 |
|---|---|---|
| `carte_A.pgm` | 34 735 o | `cf3ff82172d451cd51d54972ffdd1b03` |
| `carte_B.pgm` | 32 815 o | `cea7e4ad459eab80a931b07986483a3e` |
| `carte_A.yaml` | 147 o | `076d952f86644474933b1bed8bc0dfe9` |
| `carte_B.yaml` | 147 o | `db0888c14c9586bfca416c1db7448196` |
| `ab_slam_2026-11-23.png` (figure de ce rapport) | 46 606 o | `39e525bb5a761bf29057b47d479564ef` |
| `comparaison_A_B.png` (figure ad hoc antérieure, non versionnée) | 18 012 o | `8c531ced003f3a0a1ad0981bd4c6aebe` |

Journaux de passe d'origine : `/tmp/ab_slam/*.log` (volatile — non conservés).

## 8. Note de provenance

La figure ad hoc antérieure (`comparaison_A_B.png`) annonce en légende la variante B comme
« 0,1 s / 5 cm / **0,6 m** ». Le harnais qui a produit les cartes
(`correlation_search_space_dimension:=0.8`) et l'unité en production portent **0,8** : la
légende de cette figure est fausse, écrite à la main dans un script non versionné. La figure
de ce rapport est régénérée depuis les `.pgm` et n'affiche que des valeurs recalculées. La
conclusion ne dépend pas de la légende : elle repose sur le comptage des cellules isolées.
