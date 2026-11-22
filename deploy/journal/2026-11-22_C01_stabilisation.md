# C01 — Stabilisation de la production et séparation des arbres

**Date :** 2026-11-22 · **Branche :** `ops/REQ-OPS-050-stabilisation` (depuis `main` = `1111bee`)
**Arbre :** `/home/jetson/clawbot-dev` (worktree) · **Production :** `/home/jetson/clawbot`, détachée sur `prod-20261122-p13`

## 0. Point bloquant, en tête

**Deux gestes restent non faits, faute d'accord :** `sudo systemctl daemon-reload` et
`sudo systemctl start clawbot-mission-executive`. La question a été posée à l'opérateur à
21:52 ; **le délai a expiré sans réponse, ce qui n'est pas un accord**. Conséquence :
`smoke_check.sh` reste à **3 échecs** (NeedDaemonReload, `execute_mission` absente,
`/clawbot/mission/decide` absent) et **aucune mission ne peut encore s'exécuter**.

Raison de la porte : le bras n'est pas au repos. Mesure du 2026-11-22 21:52 sur
`/arm/servo_angles` (domaine 28, 9,94 Hz) : `[96, 171, 0, 15, 90, 6]` contre la référence
`[90, 180, 0, 0, 90, 149]` ±5° — quatre articulations hors bande, pince fermée. La condition
posée par l'opérateur (« si le bras est au repos ») n'était pas remplie.

## 1. Phase A — faits (lecture seule)

Artefacts complets : `~/clawbot_ops/C01/A1…A9` (hors dépôt).

| ID | Constat | Preuve |
|---|---|---|
| A1 | **4 liens pendants** : `clawbot-lidar`, `ros2-llm-bridge`, `rosbridge`, `yolo-detector` → `/home/jetson/clawbot/services/…` supprimés par P14 | `find /etc/systemd/system -maxdepth 1 -xtype l` |
| A2 | **21 unités** en `NeedDaemonReload=yes` : le fichier sur disque est celui de P14, la configuration chargée est celle d'avant | `systemctl show -p NeedDaemonReload` |
| A2b | **2 cibles ExecStart absentes** : `launch/robot_description.launch.py` (`clawbot-description`, active) et `ros2_llm_bridge/hardware_service.py` (`ros2-hardware-service`, active) | `[ -e <chemin> ]` |
| A3 | Les 17 processus tournent sur des **fichiers supprimés** ou des copies d'`install/` ; démarrages en trois vagues (12:59, 16:32, 18:27-18:59) ; aucun redémarrage du Jetson depuis le 2026-11-15 12:02 | `ps -o lstart=`, `/proc/<pid>/exe` |
| A4 | `install/` est une **copie** (0 symlink) ; paquets datés 10:14–18:36 ; **aucun paquet reconstruit après 19:00** ; `install/clawbot_bringup` **absent** | `find install -mindepth 1 -maxdepth 1 -printf …` |
| A5 | **58 suppressions, 6 modifications, 12 fichiers non suivis** ; `joy_teleop` réécrit (21:11), `config/manette.yaml` régénéré le 15/11, suppressions `yahboomcar_description` avec dossiers datés de **mars 2026** | `git status --porcelain=v1`, `stat` |
| A6 | **`DEPLOYED=1111bee`** (voir §2) | croisement A3/A4/journaux |
| A7 | À `1111bee`, **toutes** les cibles existent ; dans l'arbre courant, **aucune** | `git cat-file -e 1111bee:<chemin>` |
| A9 | Les 18 `ExecStart` chargés sont **identiques en substance** aux fichiers de `1111bee` (seules diffèrent des commentaires, des continuations de ligne et des clés `Restart=`) | comparaison normalisée, `~/clawbot_ops/C01/A9_compare_ExecStart.txt` |

### Risque au prochain redémarrage — avant

**16 unités actives KO, 1 OK** (`yahboom_oled`, fichier réel dans `/etc`), **4 liens
pendants**. Toutes les autres seraient lancées, après un `daemon-reload`, avec
`ros2 launch clawbot_bringup …` alors que `install/clawbot_bringup` n'existe pas.

## 2. `DEPLOYED` et sa preuve

**`DEPLOYED=1111bee`** — fin de P13, 2026-11-22 20:28:09 +0100.

1. Aucun paquet d'`install/` n'a été reconstruit après 19:00 ; le premier commit de P14 est
   `3cb7daa` à 20:35:22. Aucun code de P14 n'est donc installé.
2. `install/clawbot_bringup` est absent, alors que chaque unité P14 le lance.
3. C'est le dernier commit dont l'arbre contient **toutes** les cibles citées par les
   unités chargées et par les processus vivants (A7).
4. **Réserve, non masquée :** `install/` n'est pas une construction pure de `1111bee`.
   Il contient le déplacement `preconditions.py` de P13 (paquet daté 15:55) mais **pas**
   l'`initial_positions` de P13 (`install` porte `[-0.244346, 0.122173, 0, 0, 0]`, le
   dépôt `[0, 1.5708, -1.5708, -1.5708, 0]`), et il contient `yolo_node` de P12 (18:36,
   commit `9168970` à 19:15). Les services concernés sont inactifs ou inchangés :
   choisir `1111bee` ne change aucun binaire en service.

## 3. Décisions de l'opérateur

| Question | Réponse | Heure |
|---|---|---|
| `joy_teleop/`, `config/manette.yaml`, `manipulation_moveit.md` sont-ils de vous ? | **oui** (calibration manette du 15/11 et reprise du dossier `joy_teleop`) | 21:47 |
| Suppressions dans `yahboomcar_description` voulues ? | **oui** (variantes R2/X3/Ackermann inutilisées) | 21:47 |
| Go phase B ? | **oui** | 21:47 |
| Go phase C ? | **oui** (robot immobile, aucune mission) | 21:50 |
| Start de l'exécutif si le bras est au repos ? | condition posée ; **bras hors enveloppe**, question de dépassement **sans réponse** | 21:52 |
| `daemon-reload` ? | **sans réponse** | 21:52 |

## 4. Phase B — mise à l'abri

```
branche wip/arbre-2026-11-22, commit unique « wip: état de l'arbre de travail au 2026-11-22
avant C01, non relu [C01] », 58 D + 6 M + 12 non suivis
git status --porcelain : vide
retour sur refactor/REQ-OPS-040-demarrage (2c2d1d7) — branche P14 intacte
```

Fichiers mis à l'abri : `config/manette.yaml`, `joy_teleop/README.md`,
`joy_teleop/clawbot_restart_teleop.sh`, `joy_teleop/identify_mapping.py`,
`joy_teleop/pair_procontroller.sh`, `docs/knowledge-base/02_Software/manipulation_moveit.md`,
25 STL et 33 URDF/xacro de `yahboomcar_description` (+ `yahboomcar_description_x1`).

## 5. Phase C — bascule de la production (partielle)

| Étape | État |
|---|---|
| Sauvegarde | **faite** — `~/clawbot_backups/2026-11-22-214644` (94 Mo ; `commit_precedent.txt` = `2c2d1d7`, `install.tgz`, `unites.txt`, `liens_etc.txt`). Espace libre 47 Go avant |
| Bascule | **faite** — `git checkout --detach 1111bee`, tag `prod-20261122-p13` |
| Revérification A1/A2 | **faite** — **0 lien pendant**, **toutes les cibles ExecStart présentes**, `NeedDaemonReload=yes` sur 21 unités (attendu : le dernier rechargement est antérieur à plusieurs commits) |
| Reconstruction | **aucune** — A4 ne montre aucun paquet modifié après 19:00 |
| `daemon-reload` | **NON FAIT** — accord sans réponse |
| `start clawbot-mission-executive` | **NON FAIT** — bras hors enveloppe, accord sans réponse |
| `smoke_check.sh` | **3 échecs** (voir §0) |

### Risque au prochain redémarrage — après

**0 lien pendant, 0 cible absente.** Les 21 unités restent en `NeedDaemonReload=yes`
jusqu'au rechargement : leur prochain démarrage utilisera les fichiers de `1111bee`, dont
les `ExecStart` sont identiques en substance à ceux qui tournent (A9). Le risque « le robot
ne redémarre plus » est levé ; le risque « le robot redémarre avec une configuration
différente de celle chargée » reste, borné aux clés `Restart=`, aux commentaires et au
durcissement ajoutés entre le dernier rechargement et `1111bee`.

### `smoke_check.sh` 1.1.0 — sortie au 2026-11-22 21:50

```
OK     arbre de production sans modification suivie
OK     production sur le tag prod-20261122-p13
OK     aucun lien d'unité pendant
ECHEC  fichier d'unité changé depuis le chargement (NeedDaemonReload) : 21 unités
OK     toutes les cibles ExecStart existent
OK     aucune unité du robot en échec
OK     nœud /driver_node, /safety_arbitrator, /director, /ydlidar_ros2_driver_node, /ekf_filter_node présents
OK     action /clawbot/execute_skill servie
ECHEC  action /clawbot/execute_mission absente
OK     service /clawbot/capabilities/list servi
ECHEC  service /clawbot/mission/decide absent
OK     /scan 10,123 Hz · /imu/data_raw 10,000 · /joint_states 20,000 · /director/state 5,000
OK     /cmd_vel_safe 19,997 · /safety/state 20,005 · /voltage 10,021 · /odom 9,998
OK     /cmd_vel_safe : 1 éditeur
```

## 6. Phase D — arbre de développement et `main`

| Étape | État |
|---|---|
| Worktree | `git worktree add /home/jetson/clawbot-dev refactor/REQ-OPS-040-demarrage` — **fait** |
| `main` | `main` (`7344951`) était un ancêtre de `1111bee` : `git branch -f main 1111bee` (**avance de 210 commits, sans réécriture**) |
| Tags | `rel-P13` → `1111bee` ; `prod-20261122-p13` → `1111bee` (arbre de production) |
| Branche de travail | `ops/REQ-OPS-050-stabilisation` depuis `main` |
| Exigences | REQ-OPS-050, 051, 052 ajoutées à `requirements/OPS.yaml` |
| Fusion dans `main` | **NON FAITE** — attend l'acceptation de l'opérateur |

## 7. Paquets reconstruits

**Aucun.** A4 : aucun dossier de paquet d'`install/` n'a été modifié après 19:00, et
`ros2_llm_bridge_cpp` date de 10:15 (avant P14). Le contrôle `colcon list` à `1111bee`
donne 46 paquets, dont les 29 déplacés sous `attic/` par P14 — ils sont tous encore dans
l'arbre de production, ce qui est l'état attendu de `1111bee`.

## 8. Sécurité

- Publication dans le domaine 28 : **non**. Deux lectures seulement : `ros2 topic info`
  et `ros2 topic echo --once` sur `/arm/servo_angles`.
- `/etc` modifié ? **non**. Aucun `systemctl` de mutation : le `daemon-reload` et le `start`
  demandés n'ont pas été exécutés faute d'accord.
- Arbre de production : détaché sur `prod-20261122-p13`, `git status --porcelain` vide.
- Redémarrage du Jetson : **non**.
- Processus laissé : aucun (les collectes sont des commandes courtes).

## 9. `scripts/check.sh` dans l'arbre de développement — 2 échecs, antérieurs à C01

```
2 failed, 814 passed, 14 skipped, 8 xfailed in 97.37s   EXIT=1
FAILED clawbot_director/test/test_nav2_config.py::test_la_carte_chargee_est_celle_du_catalogue
FAILED tests/test_cmd_vel_scaling.py::test_feedback_sign_matches_command
```

Aucun des deux n'est introduit par C01 : le commit C01 ne contient que des exigences et de
la documentation. Les deux sont reproduits à l'identique dans l'arbre de production détaché
sur `1111bee`, et avec un environnement propre (`env -i`, overlay du seul arbre de dev).

1. **`test_la_carte_chargee_est_celle_du_catalogue`** — `config/nav2_clawbot.yaml` porte un
   chemin **absolu** : `yaml_filename: /home/jetson/clawbot/maps/test_cartographie_apres_deplacement.yaml`.
   Le test compare cette valeur à `RACINE/"maps"/…`, où `RACINE` est la racine de l'arbre
   courant : il ne peut passer que dans `/home/jetson/clawbot`. C'est exactement le défaut
   que la séparation des arbres rend visible ; il vient de P07 et non de C01.
   *Hors périmètre C01 : à corriger en P14b.*
2. **`test_feedback_sign_matches_command`** — `feedback(-0.843)` rend `-0.843`, le test
   attend `> 0` (`tests/test_cmd_vel_scaling.py:38`). Échec identique dans les deux arbres :
   il ne dépend ni du chemin ni de l'installation. *Cause non établie ; à instruire.*

Conséquence assumée : le critère « `scripts/check.sh` sort 0 sur cette branche » **n'est
pas tenu**, pour deux raisons extérieures au contenu de C01. La branche est donc committée
mais **non fusionnée** dans `main`.
