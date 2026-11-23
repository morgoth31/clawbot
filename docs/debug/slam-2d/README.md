# Debug — qualité du SLAM 2D (Clawbot X3 Plus)

Document de reprise. Objectif : qu'une personne qui n'a pas suivi ces sessions puisse
comprendre **où en est le problème**, **ce qui a déjà été éliminé et pourquoi**, **où sont les
données**, et **quelle mesure faire ensuite**. Tout ce qui est écrit ici est mesuré ; les
raisonnements non vérifiés sont explicitement marqués « hypothèse ».

Dernière mise à jour : 2026-11-23 12:55 CET.

---

## 1. Le problème, et comment on le juge

**Symptôme.** La carte produite en cartographie réelle porte des murs localement dédoublés, un
éventail de rayons qui partent des murs, et une moucheture de points isolés autour des
contours. Ce n'est pas une pièce dessinée deux fois : c'est un contour épais, bruité, avec des
traits noirs parallèles et décalés.

**Indicateur retenu.** Le nombre de **cellules occupées isolées** : une cellule occupée sans
aucun voisin occupé dans son 3×3 n'est pas un mur, c'est un écho mal apparié. C'est le meilleur
proxy disponible du bruit d'appariement sur un `.pgm` de `map_server`, et il est insensible à
la taille du cadre.

Métriques secondaires : cadre (`largeur × hauteur × résolution²`), cellules connues et leur
part (information perdue ou non), cellules occupées.

**Convention de lecture des `.pgm`** produits par notre sauveur : `0` = occupé, `255` = libre,
`205` = **inconnu**. Piège : `205 < 250` — compter les pixels « < 250 » comme connus donne des
chiffres faux (68 % au lieu de 42 % sur la carte du 23/11).

**Objectif fixé** : descendre sous **1,5 %** de cellules isolées sur la vraie carte, et si
possible sous 1 %, **avec une explication du mécanisme**. La configuration actuelle donne
1,36 % en rejeu et 3,23–3,84 % sur le robot : c'est tout le problème.

---

## 2. État de la question

| Élément | État |
|---|---|
| Chaîne capteurs → SLAM | **saine et vérifiée** (`/scan` 10 Hz `laser_link`, TF complète, `map → odom` publiée, 1 seul éditeur `/map`) |
| Sauvegarde de la carte | **fonctionne** (service `SaveMap` → `result=0` + fichiers réellement écrits) |
| Signe du lacet (IMU vs roues) | **hors de cause**, prouvé (§4.1) |
| Bras dans le champ du lidar | **hors de cause**, mesuré (§4.2) |
| Prédiction de l'EKF (glissement mécanum) | **rien ne la désigne comme fautive** à l'échelle mesurable (§4.3) |
| Causes restantes | **distorsion du scan en rotation** (piste principale) ; rastérisation **écartée** (§5) |
| Reproductibilité des mesures | **mauvaise** : 2,5× d'écart entre deux rejeux identiques (§6) |
| Configuration en production | `rel-C05a` : `minimum_time_interval 0.1`, `minimum_travel_distance/heading 0.05`, `correlation_search_space_dimension 0.8` |

**Résultat de la campagne de rejeux (9 configurations, 4 passes de contrôle) : aucune ne bat la
configuration en production.** Le meilleur jeu est donc celui qui est déjà en service, et il n'y a
**aucun patch à appliquer**. Le problème n'est pas un réglage manquant : il est dans la
reproductibilité (§6) et, très probablement, dans la distorsion du scan en rotation (§5, H5).

---

## 3. Les mesures, avec leur fiabilité

| # | Mesure | Valeur | Source | Fiabilité |
|---|---|---|---|---|
| 1 | Carte réelle 23/11 (anciens réglages) | 183×189 = 86,5 m² · 12 639 connues · 2 690 occupées · **87 isolées = 3,23 %** | `/var/lib/clawbot/test_data/carte_slam2d.pgm` | solide, une passe |
| 2 | Carte réelle 23/11 12:01 (réglages denses) | 260×259 = 168,4 m² · 38 094 connues · 6 987 occupées · **268 isolées = 3,84 %** | `carte_slam2d_20261123_cloture.pgm` | solide, **mais parcours différent** (3× plus de surface) |
| 3 | Rejeu A (0,5 s / 0,10 m / 0,5 m) | 160×217 = 86,8 m² · 3 361 occupées · **108 isolées = 3,21 %** | `mesures_ab/carte_A.pgm` | **une seule passe** — voir §6 |
| 4 | Rejeu B (0,1 s / 0,05 m / 0,8 m) | 160×205 = 82,0 m² · 3 449 occupées · **47 isolées = 1,36 %** | `mesures_ab/carte_B.pgm` | **une seule passe** — voir §6 |
| 5 | Rejeu B, deuxième passe (R0b) | 160×205 · 3 478 occupées · **45 isolées = 1,30 %** | `slam_debug/2026-11-23/rejeu_R0b_reference/` md5 `689eb1ea…` | reproduit #4 → harnais validé |
| 6 | Rejeu B, troisième passe (R0a) | 179×205 = 91,7 m² · 18 038 connues · 4 003 occupées · **120 isolées = 3,0 %** | `slam_debug/2026-11-23/rejeu_R0a_aberrant/` md5 `f7807a9c…` | **même config que #5, résultat 2,5× pire** |
| 7 | Corrélation `wz` IMU / roues / lidar | −0,980 / +0,985 / +0,981 contre le lidar ; pentes −1,004 / +1,005 / +1,004 | `scripts/arbitrage_lacet.py`, `essai_libre.py` | solide, 584 paires |
| 8 | TF `base_link → imu_link` | translation `[0.001, 0.017, 0.032]`, RPY `(−180.000°, 0.005°, −90.006°)`, colonne z = −1 | `tf2_echo` en service | fait mesuré |
| 9 | Échos proches du lidar | 25 points < 0,35 m, tous à ±120–150° (arrière), 22 sous 0,20 m | `/scan` au repos | solide |

Le point 6 est le plus important du document : **la même configuration, sur le même bag, donne
45 ou 120 cellules isolées selon la passe.** Tout chiffre unique de ce dossier doit être lu avec
cette réserve.

---

## 4. Ce qui est éliminé, et la preuve

### 4.1 Le signe du lacet n'est pas un défaut

La passation du 23/11 affirmait que `wz(IMU)` et `wz(roues)` corrèlent à −0,983, donc que l'un
des deux était inversé, et que la cap dérivait à cause de ça. **C'est faux**, et mesuré :

- La TF `base_link → imu_link` est **déclarée retournée** (colonne z = −1, cf. mesure #8).
  L'axe `+z` du robot sort en `−z` dans `imu_link` : une rotation anti-horaire **doit** y
  produire un `wz` négatif. L'accéléromètre le confirme au repos : `az = −9,979 m/s²`.
- `robot_localization` applique cette rotation avant de fusionner. Résultat mesuré sur 584
  paires en conduite libre (60 s) : la cadence de lacet de l'EKF suit le lidar avec une pente
  de **+1,004** et **98,2 %** de signes communs.
- Les roues suivent aussi (+1,005 / 95,2 %). L'IMU brute est à −1,004 / 3,0 % **dans son propre
  repère**, ce qui est correct.

**Conséquence : ne corrigez pas le signe.** Retourner `gz` à la publication rendrait
`/imu/data_raw` incohérent avec son repère déclaré et ferait partir l'EKF du mauvais côté.
La corrélation −0,983 comparait deux repères différents.

Traces : `docs/audit/2026-11-23-signe-lacet/note.md`, `tests/hardware/HW-DRV-002.md`
(essai physique du 23/11, deux rotations annoncées + 60 s libres), `REQ-DRV-018`.

### 4.2 Le bras ne salit pas la carte

25 points sous 0,35 m seulement, tous à l'arrière (±120–150°), 22 sous 0,20 m donc éliminés par
`min_laser_range 0.15`. Le lidar ne voit pas le bras. Ce n'est pas lui qui crée l'éventail de
rayons.

### 4.3 La prédiction de l'EKF n'est pas désignée

Analyse amont par appariement polaire conjoint `(dθ, dx, dy)` entre scans espacés (3 006
paires, instrument auto-testé) :

- composante **latérale** : `lidar = 0,961 × prédiction − 0,3 mm`, corrélation 0,902 → la
  prédiction latérale est fidèle à ~4 %, **pas de glissement latéral mesurable** ;
- composante **avant** : non mesurable avec cet instrument (la marche le long d'un mur est
  invisible dans les portées, défaut documenté par auto-test) — **aucune conclusion** contre
  l'EKF ;
- erreur médiane par paire ~20 mm en mouvement, indépendante du niveau de rotation (21,4 mm à
  |ω| < 0,1 ; 20,4 mm à 0,3–0,6 ; 7,2 mm à > 0,6) → au niveau du bruit de l'instrument.

Traces : `slam_debug/2026-11-23/outils/analyse_translation.py`, `analyse_translation.out`.

---

## 5. Piste principale ouverte : la rastérisation, pas seulement le graphe

Faits de source (slam_toolbox 2.6.10, `SMapper::getOccupancyGrid` / `Mapper.cpp` /
`laser_utils`) :

1. **La carte est entièrement re-rastérisée à chaque mise à jour** depuis *tous* les scans aux
   poses optimisées courantes. Il n'y a pas d'accumulation incrémentale : la qualité de la
   carte est exactement celle du graphe de poses.
2. Une cellule est marquée occupée si `passes > min_pass_through` **et**
   `hits / passes > occupancy_threshold`. Défauts dans le YAML amont :
   `min_pass_through = 2`, `occupancy_threshold = 0.1`.
3. **Conséquence** : une cellule traversée par un rayon parasite **une fois sur neuf** est
   marquée occupée. Or `nav2`/`map_server` relit ces cartes avec `occupied_thresh 0.65` — le
   YAML que notre sauveur écrit le dit lui-même. Les deux seuils ne parlent pas du même objet :
   `slam_toolbox` décide ce qui est occupé *dans son OccupancyGrid*, `map_server` décide ce
   qu'il fait des probabilités quand il relit un `.pgm`.

**Verdict après essai — l'hypothèse est réfutée.** Quatre variantes testées sur le bag :

| Réglage | Occupées | Isolées | Effet |
|---|---|---|---|
| `occupancy_threshold 0.65` | **0** | 0 | carte vidée (ratio plafonné à 0,5) |
| `occupancy_threshold 0.40` | 551 (−84 %) | 18 | détruit les murs |
| `occupancy_threshold 0.20` | 1 596 (−54 %) | 41 | détruit la moitié des murs pour −6 isolées |
| `min_pass_through 4` | 3 365 (−3,2 %) | 60 (1,78 %) | fait **monter** la part d'isolées |

Le seuil ne sépare rien : la moucheture a des **ratios d'impact comparables à ceux des murs**.
Ce ne sont donc pas des impacts parasites faibles, mais des **placements systématiques** — ce que
produit un scan étalé pendant la rotation (§10, H5). Et comme la carte est re-rasterisée depuis
tous les scans aux poses optimisées, aucun filtre de rastérisation ne peut les retirer sans
emporter les murs. Corollaire : la convention `nav2` de 0,65 est **inapplicable aux grilles
karto**.

Contre-hypothèse à ne pas perdre : si la carte est re-rastérisée depuis le graphe, un graphe
mal optimisé produit exactement les mêmes symptômes. Le départage se fait en regardant si les
murs doublés sont **locaux** (quelques endroits, là où une boucle s'est mal fermée) ou
**partout** (alors c'est la rastérisation ou la prédiction).

---

## 6. Le piège de méthode : deux rejeux identiques ne donnent pas la même carte

```
R0b : 160×205 · 3 478 occupées ·  45 isolées (1,30 %)   md5 689eb1ea74b797ca3a165b810afb38cc
R0a : 179×205 · 4 003 occupées · 120 isolées (3,00 %)   md5 f7807a9c5fce34ec1d072892a17c519c
```

Même bag (md5 vérifié : le `.db3` est identique à la décompression du `.zstd`), même
configuration, même EKF, même harnais. Signature du rejeu aberrant observée : **cadre élargi de
19 cellules, cellules connues +29 %, origine décalée de 1,42 m en x.** Un rejeu sur 1,5 s de
décalage dans l'ordre des messages suffit visiblement à changer la trajectoire estimée.

Conséquences pratiques :

- **Ne concluez jamais sur une seule passe.** Deux passes minimum par variante retenue, et
  publiez la dispersion, pas seulement la meilleure valeur.
- **L'A/B 108 → 47 qui a justifié la mise en production des paramètres denses repose sur une
  passe par variante.** Avec un facteur 2,5 possible entre deux passes identiques, il ne prouve
  pas ce qu'on lui a fait dire. C'est une faiblesse de ce dossier, pas une preuve contraire.
- Si un rejeu donne un cadre nettement plus large et plus de cellules connues que la référence,
  **le jeter** et le rejouer avant de mesurer.

---

## 7. Où sont les données

### 7.1 Durables (hors `/tmp`)

| Chemin | Contenu | Taille / md5 |
|---|---|---|
| `/var/lib/clawbot/test_data/slam2d_piece/` | **bag de référence**, 298 s, `/scan` `/odom_raw` `/imu/data_raw` `/tf_static` | `.db3` 65 253 376 o (+ `.zstd` 8,7 Mo) |
| `…/slam2d_piece_0.db3` | lecture directe pour l'analyse | md5 du contenu décompressé `d17b2d32…` |
| `/var/lib/clawbot/test_data/carte_slam2d.pgm` | carte réelle 23/11, anciens réglages | md5 `f38566913dc6e67b8b5c9f38d1d454e2` |
| `/var/lib/clawbot/test_data/carte_slam2d_20261123_cloture.pgm` | carte réelle 23/11 12:01, réglages denses | md5 `7b87cf3b57cf3eec33adc22058e4c3a3` |
| `/home/jetson/clawbot_fonctions/mesures_ab/` | cartes A et B du test hors robot, `.yaml`, figures | A `cf3ff821…` (34 735 o), B `cea7e4ad…` (32 815 o) |
| `/home/jetson/clawbot_fonctions/slam_debug/2026-11-23/` | **copie de sécurité** des deux rejeux R0a/R0b, des cartes réelles, de l'analyse de translation et du journal d'essais | voir §7.3 |

### 7.2 Outils (dans le dépôt, branches indiquées)

| Outil | Rôle | Branche |
|---|---|---|
| `scripts/ab_slam_toolbox.sh` | harnais de rejeu A/B (shim TF, EKF, SLAM, sauvegarde pendant le rejeu, nettoyage) | `docs/REQ-DRV-012-ab-slam-2d` |
| `scripts/sauve_carte.py` | écrit `/map` en PGM+YAML (le `map_saver` de slam_toolbox échoue en rejeu) | idem |
| `scripts/compare_cartes_ab.py` | métriques dont les cellules isolées | idem |
| `scripts/compare_cartes_figure.py` | figure de comparaison, libellés recalculés | idem |
| `scripts/arbitrage_lacet.py` | appariement polaire sur bag, 3 sources | `fix/REQ-DRV-018-signe-lacet` |
| `scripts/polarite_scan.py` | polarité du repère `/scan` | idem |
| `scripts/essai_libre.py` | arbitrage en direct sur conduite libre | idem |
| `scripts/mesure_signe_lacet.py` | mesure du signe avec plan annoncé | idem |
| `scripts/pose_map.py` | pose `map → base_link` moyennee (bouclage) | idem |
| `scripts/analyse_cap.py` | cap EKF contre cap lidar (rejeu) | idem |
| `scripts/enregistre_odom.py` | enregistre `/odom` d'un rejeu (refuse de conclure si vide) | idem |

⚠️ **Les outils ne sont pas tous sur la même branche.** Dans l'arbre de travail courant
(`fix/REQ-DRV-018-signe-lacet`), les quatre premiers sont absents. Les récupérer avec :
`git -C /home/jetson/clawbot-dev show docs/REQ-DRV-012-ab-slam-2d:scripts/ab_slam_toolbox.sh > /tmp/x.sh`

Copies équivalentes et immédiatement utilisables dans `/home/jetson/.hermes/cache/scratch/` :
`ab_slam2.sh` (celui qui a produit A et B), `sauve_carte.py`, `compare_cartes_ab.py`,
`compare_cartes_figure.py`.

### 7.3 Arborescence de `clawbot_fonctions/slam_debug/2026-11-23/`

```
cartes_reelles/       carte_slam2d.pgm          (23/11, anciens réglages)
                      carte_slam2d_20261123_cloture.pgm (23/11 12:01, réglages denses)
rejeu_R0a_aberrant/   carte_B.pgm  f7807a9c…    + slam/play/save/shim/ekf logs
rejeu_R0b_reference/  carte_B.pgm  689eb1ea…    + mêmes logs
outils/               resultats.md (journal d'essais du sous-agent)
                      analyse_translation.py / .out
                      ab_slam_toolbox.sh
```

### 7.4 Volatils — à sauver avant usage

`/tmp/glm/` (rejeux en cours, journal), `/tmp/lacet_R1.*`, `/tmp/essai_libre.log`,
`/home/jetson/.hermes/cache/scratch/` (purgé après 24 h d'inactivité).

---

## 8. Reproduire

Les commandes ci-dessous supposent `ROS_DOMAIN_ID=99` et :

```bash
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=99
```

**Un rejeu complet (~5 min 10) et sa mesure :**

```bash
scripts/ab_slam_toolbox.sh B --out /tmp/ab_slam        # B = réglages de production
/usr/bin/python3 scripts/compare_cartes_ab.py /tmp/ab_slam/carte_B.pgm /tmp/ab_slam/carte_B.pgm
```

**Mesurer une carte quelconque :**

```bash
/usr/bin/python3 scripts/compare_cartes_ab.py <carte.pgm> <carte.pgm> 0.05
```

**Vérifier la polarité du lidar (pas nécessaire si vous refaites une vraie passe) :**

```bash
/usr/bin/python3 scripts/arbitrage_lacet.py /var/lib/clawbot/test_data/slam2d_piece/slam2d_piece_0.db3 /tmp/lacet.csv
/usr/bin/python3 scripts/polarite_scan.py  /var/lib/clawbot/test_data/slam2d_piece/slam2d_piece_0.db3
```

**Cartographie réelle (robot) :** arrêter `clawbot-slam`, redémarrer pour partir d'une carte
vide, relever `pose_map.py --label depart`, laisser l'opérateur rouler 3–5 min **en revenant
exactement au point de départ, marque au sol**, relever `--label retour`, puis :

```bash
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap "{name: {data: '/var/lib/clawbot/test_data/carte_<date>'}}"
ls -l /var/lib/clawbot/test_data/carte_<date>.*     # vérifier que les fichiers existent
```

---

## 9. Pièges qui coûtent du temps (tous rencontrés)

1. **Sauvegarder après la fin du bag** : `/clock` s'arrête, les nœuds gèlent, `map_saver` rend
   `result=255`. Sauvegarder **pendant** le rejeu (t+292 s pour ce bag).
2. **`kill` sur `ros2 run` ne tue que le lanceur**, pas l'enfant. Lancer sous `timeout`, et
   avant tout kill massif lire `/proc/<pid>/environ` pour ne viser que le domaine 99.
3. **`ros2 node list` / `ros2 topic info` mentent juste après un redémarrage** : la découverte
   DDS garde les nœuds morts. `/map` a affiché 2 éditeurs 10 s après un `restart` alors qu'il
   n'y en avait qu'un.
4. **Un `ekf_node` en `use_sim_time` lancé avant le bag ne publie jamais** : le bag porte une
   horloge simulée 37 000 s en arrière, l'EKF journalise « Detected jump back in time » puis
   reste muet. Ordre correct : `ros2 bag play --clock` d'abord, EKF ensuite. Un CSV `/odom`
   vide ne dit pas « pas de dérive », il dit « rien n'a été mesuré ».
5. **La garde de démarrage du harnais est trop courte** : « Using solver plugin » a mis 14 s à
   apparaître sur une machine chargée, le harnais a conclu à tort « n'a pas démarré ». Boucler
   jusqu'à 30 s.
6. **Deux rejeux concurrents dans le même domaine se mélangent** : un seul à la fois.
7. **`map_saver` de slam_toolbox échoue en rejeu** : utiliser `sauve_carte.py` (QoS
   `TRANSIENT_LOCAL`).
8. **Un fichier `.pgm` de 205 comme « inconnu »** : ne pas le compter comme connu.
9. **Un rejeu peut être aberrant** (cadre élargi, connues en hausse) : le jeter et le refaire
   avant de mesurer (§6).

---

## 10. Questions ouvertes, et la prochaine mesure qui tranche

| Question | Test qui tranche | Coût |
|---|---|---|
| **Pourquoi une passe sur deux diverge-t-elle ?** | journaliser `map → odom` à chaque `map_update` sur 3–4 rejeux | 1 h |
| La moucheture vient-elle de la rotation ? | cartographier sans rotation rapide (< 0,2 rad/s) et comparer | 2 rejeux |
| La moucheture se joue-t-elle dans l'appariement ? | `link_match_minimum_response_fine` 0,1 → 0,3, deux passes | 2 × 5 min |
| Les murs doublés sont-ils locaux (boucle mal fermée) ou partout ? | cartographier la localisation des doublons sur la carte réelle, comparer à la trajectoire | 30 min |
| ~~La moucheture vient-elle du seuil de rastérisation ?~~ | ~~`occupancy_threshold`, `min_pass_through`~~ | **répondu : non** (§5) |

**Ce qui n'est pas le sujet** : `REQ-HEALTH-010` (moniteur C++) et l'échec de test nav2 sur le
chemin absolu (P14b). Aucun des deux n'affecte la qualité de la carte.

---

## 11. Journal des sessions du 2026-11-23

| Heure | Ce qui a été fait | Résultat |
|---|---|---|
| 09:13–09:23 | A/B hors robot, variantes A et B sur le bag | A 108 isolées, B 47 — **une passe chacune** |
| 11:23–11:27 | Métriques indépendantes sur A/B ; recherche de provenance | comptes reproduits ; la figure ad hoc annonçait à tort « 0,6 m » |
| 11:25–11:53 | Arbitrage hors robot (bag) : lidar comme 3e source | roues +0,958, IMU −0,953 → « sous réserve de la polarité de `/scan` » |
| 11:47 | Essai physique HW-DRV-002 (2 rotations + 60 s libres) | **aucun capteur inversé ; l'EKF a raison** ; TF `imu_link` retournée |
| 12:01 | Cartographie réelle avec les réglages de production | 3,84 % d'isolées, cadre 168 m² → **ne passe pas** |
| 12:08→ | Sous-agent glm-5.3 : rejeux en série, analyse de source | dispersion 2,5× découverte ; piste rastérisation ; essais en cours |

---

## 12. État du dépôt et de la production

- Production : `/home/jetson/clawbot` détachée sur `prod-20261123-c05a-rel` (`94eea8f`), arbre
  propre. Unités actives : `ros2-driver-node`, `clawbot-ekf`, `clawbot-safety-arbitrator`,
  `clawbot-joy-teleop`, `clawbot-slam`, `clawbot-lidar`.
- Développement : `/home/jetson/clawbot-dev`, deux branches en avance sur `main` :
  - `docs/REQ-DRV-012-ab-slam-2d` : rapport d'A/B + outils de métrique (commit `e281512`) ;
  - `fix/REQ-DRV-018-signe-lacet` : exigence, procédure HW-DRV-002 remplie, note d'arbitrage
    (commits `9424350`, `6f00b87`, `7b81196`).
- `REQ-DRV-012` est en production **sans preuve solide** (§6). Ne pas la considérer comme
  acquise, ne pas la retirer non plus avant d'avoir la mesure à deux passes.
