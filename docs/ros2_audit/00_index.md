# Audit ROS 2 — Clawbot X3 — index et registre des sources

**Poste :** Jetson Orin NX, `ROS_DOMAIN_ID=28`, ROS 2 Humble, RMW `rmw_fastrtps_cpp`
**Collecte :** 2026-11-22T10:59:33+01:00 (dynamique), 2026-11-22T10:59:10+01:00 (statique), compléments jusqu'à 11:08
**Livrables :** `01_architecture_factuelle.md`, `02_analyse_performances_et_concurrence.md`, `03_audit_robustesse_et_maintenabilite.md`, `04_cahier_entree_refonte_pour_claude.md`

## 1. Périmètre

- **Système audité :** robot Clawbot X3 sur Jetson Orin NX, ROS 2 Humble, domaine DDS 28, en fonctionnement nominal (unités systemd actives, uptime 6 j 22 h au moment de la collecte).
- **Workspace inspecté :** `/home/jetson/clawbot` (38 paquets, sans répertoire `src/` : les paquets sont à la racine), plus les paquets déployés depuis `/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws` et `/home/jetson/yahboomcar_ros2_ws/software/library_ws` (Astra, YDLidar, robot_localization).
- **Hors périmètre :** code applicatif des paquets vendor non déployés (`yahboomcar_mediapipe`, `yahboomcar_KCFTracker`, `yahboomcar_linefollow`, `slam3d`), modèle LLM distant, mécanique du bras.
- **Aucune modification** n'a été apportée au système : toutes les commandes sont en lecture (`ros2 node/topic/param list|info`, `ros2 topic hz|echo`, `systemctl show|list-units`, `journalctl`, `ps`, `df`, `ss`, `tegrastats`, `cat`). Aucun `systemctl start|stop|restart`, aucune publication sur `/cmd_vel`, aucun `ros2 param set`.

## 2. Méthode

1. **Collecte statique** (`tools/collect_static.sh`) : inventaire des `package.xml`, interfaces `.msg/.srv/.action`, launch files, YAML, unités systemd, URDF, puis greps de code (executors, groupes de callback, QoS, E/S, paramètres, TF, appels bloquants).
2. **Collecte dynamique** (`tools/collect_runtime.sh`, 6 min 15 s) : graphe du domaine 28, `node info` par nœud, QoS effectif par topic (`topic info -v`), cadences mesurées (`topic hz`), TF, processus, sockets RTPS, `doctor`, journaux d'unités.
3. **Compléments ciblés** : cadences des flux capteurs exclus de la boucle automatique (images, `/scan`, `/point_cloud`), capture de 5 s de `/tf` pour l'arbre complet, `systemctl --failed`, journal détaillé de `clawbot-sentinel`.
4. Chaque donnée reçoit un identifiant `Sxx` ci-dessous ; les quatre livrables ne citent que ces identifiants.
5. **Rejouabilité :** relancer `tools/collect_runtime.sh <dir>` sur un autre horodatage reproduit les mêmes artefacts. Toute divergence entre deux collectes est un fait à documenter, pas à lisser.

**Limite de méthode, à lire avant les tableaux :** la latence bout-en-bout n'est instrumentée nulle part sur ce système. `ros2 topic hz` fournit une cadence et un écart-type d'inter-arrivée, pas un temps de traversée. Toute case « latence » de ce dossier vaut donc `[NON OBSERVÉ / À VÉRIFIER]` avec sa recette.

**Sources documentaires antérieures :** `docs/knowledge-base/02_Software/` (base OKF) contient des mesures des 2026-11-10/11. Elles n'ont pas été utilisées comme sources : chaque fait de ce dossier vient des artefacts ci-dessous.

## 3. Registre des sources

| ID | Donnée | Commande exacte | Artefact | Horodatage |
|---|---|---|---|---|
| S01 | Nœuds actifs du domaine 28 | `ros2 node list` | `raw/20261122-105910/runtime/01_nodes.txt` | 2026-11-22T10:59:33+01:00 |
| S02 | Éditeurs, abonnés et services de chaque nœud | `ros2 node info <nœud>` (boucle sur S01) | `raw/20261122-105910/runtime/02_node_info.txt` | 2026-11-22T10:59:41+01:00 |
| S03 | Topics et types | `ros2 topic list -t` | `raw/20261122-105910/runtime/03_topics_types.txt` | 2026-11-22T10:59:41+01:00 |
| S04 | Services et types | `ros2 service list -t` | `raw/20261122-105910/runtime/04_services.txt` | 2026-11-22T10:59:41+01:00 |
| S05 | Actions disponibles | `ros2 action list -t` | `raw/20261122-105910/runtime/05_actions.txt` | 2026-11-22T10:59:41+01:00 |
| S06 | Paramètres par nœud | `ros2 param list` | `raw/20261122-105910/runtime/06_params_liste.txt` | 2026-11-22T10:59:41+01:00 |
| S07 | QoS effectif par topic | `ros2 topic info -v <topic>` (boucle sur S03) | `raw/20261122-105910/runtime/07_topics_info_v.txt` | 2026-11-22T11:00:30+01:00 |
| S08 | Cadence par topic (39 topics) | `ros2 topic hz <topic>` (7 s par topic) | `raw/20261122-105910/runtime/08_topics_hz.txt` | 2026-11-22T11:05:20+01:00 |
| S09 | Cadence des flux capteurs (`/scan`, images, nuages) | `ros2 topic hz` ciblé (7 s, puis 12 s pour la profondeur) | `raw/20261122-105910/runtime/17_hz_capteurs.txt` | 2026-11-22T11:06:40+01:00 |
| S10 | TF statiques (`/tf_static`, un message) | `ros2 topic echo /tf_static --once` | `raw/20261122-105910/runtime/09_tf_static.txt` | 2026-11-22T11:05:40+01:00 |
| S11 | TF dynamiques sur 5 s (arbre complet) | `ros2 topic echo /tf` (5 s) | `raw/20261122-105910/runtime/18_tf_flux_complet.txt` | 2026-11-22T11:06:20+01:00 |
| S12 | CPU, RSS et ligne de commande des processus | `ps -eo pid,ppid,pcpu,pmem,rss,etimes,comm,args --sort=-pcpu` | `raw/20261122-105910/runtime/10_processus.txt` | 2026-11-22T11:05:40+01:00 |
| S13 | Occupation disque et `/dev/shm` | `df -h / /dev/shm` | `raw/20261122-105910/runtime/11_disque_shm.txt` | 2026-11-22T11:05:40+01:00 |
| S14 | Sockets UDP RTPS ouverts | `ss -uan \| grep -E ':(7400\|7401\|741[0-5])'` | `raw/20261122-105910/runtime/12_udp_rtps.txt` | 2026-11-22T11:05:40+01:00 |
| S15 | Interfaces et compteurs réseau | `ip -s link show` | `raw/20261122-105910/runtime/12_net.txt` | 2026-11-22T11:05:40+01:00 |
| S16 | RAM, électricité, fréquences CPU, températures, `GR3D_FREQ` | `tegrastats --interval 1000` (6 s) | `raw/20261122-105910/runtime/14_tegrastats.txt` | 2026-11-22T11:05:34+01:00 |
| S17 | Distribution, middleware, versions | `ros2 doctor --report` | `raw/20261122-105910/runtime/15_doctor.txt` | 2026-11-22T11:05:50+01:00 |
| S18 | 40 dernières lignes de journal par unité active | `journalctl -u <unité> -n 40` (boucle) | `raw/20261122-105910/runtime/16_journaux.txt` | 2026-11-22T11:05:50+01:00 |
| S19 | Journal complet de `clawbot-sentinel` depuis 10:00 | `journalctl -u clawbot-sentinel --since "2026-11-22 10:00"` | `raw/20261122-105910/runtime/20_journal_sentinel.txt` | 2026-11-22T11:08:10+01:00 |
| S20 | Contexte de la collecte dynamique (domaine, RMW, charge, uptime) | `date`, `uptime -p`, `cat /proc/loadavg`, `env` | `raw/20261122-105910/runtime/00_meta.txt` | 2026-11-22T10:59:33+01:00 |
| S21 | Paquets sur disque (nom, version, chemin) | `find . -name package.xml` + `sed` sur `<name>`/`<version>` | `raw/20261122-105910/static/02_packages.tsv` | 2026-11-22T10:59:10+01:00 |
| S22 | Contenu des interfaces maison | `find . -name '*.msg' -o -name '*.srv' -o -name '*.action'` puis `cat` | `raw/20261122-105910/static/03_interfaces_contenu.txt` | 2026-11-22T10:59:10+01:00 |
| S23 | Launch files et structures déclarées | `find . -name '*.launch.py'` + `grep -E 'Node\(\|ComposableNode\|LifecycleNode\|executor'` | `raw/20261122-105910/static/04_launch_structures.txt` | 2026-11-22T10:59:10+01:00 |
| S24 | QoS déclaré dans les YAML | `grep -rn 'reliability\|durability\|depth\|qos_overrides' --include='*.yaml'` | `raw/20261122-105910/static/05_yaml_qos.txt` | 2026-11-22T10:59:10+01:00 |
| S25 | Propriétés des unités systemd actives | `systemctl show <unité> -p Restart -p Requires -p Conflicts -p ExecStart -p Environment …` | `raw/20261122-105910/static/06_units_proprietes.txt` | 2026-11-22T10:59:10+01:00 |
| S26 | Liens symboliques des unités | `ls -l /etc/systemd/system` | `raw/20261122-105910/static/06_units_symlinks.txt` | 2026-11-22T10:59:10+01:00 |
| S27 | Arêtes de joints URDF/xacro | `grep -rn '<joint\|<parent\|<child'` | `raw/20261122-105910/static/07_urdf_joints.txt` | 2026-11-22T10:59:10+01:00 |
| S28 | Executors et groupes de callback déclarés dans le code | `grep -rn 'MultiThreadedExecutor\|SingleThreadedExecutor\|MutuallyExclusive\|Reentrant'` | `raw/20261122-105910/static/08_executors_py.txt` | 2026-11-22T10:59:10+01:00 |
| S29 | QoS déclaré dans le code Python | `grep -rn 'QoSProfile\|ReliabilityPolicy\|DurabilityPolicy\|qos_profile'` | `raw/20261122-105910/static/08_qos_py.txt` | 2026-11-22T10:59:10+01:00 |
| S30 | Publications, abonnements, services et actions déclarés | `grep -rn 'create_publisher\|create_subscription\|ActionServer\|ActionClient'` | `raw/20261122-105910/static/08_io_py.txt` | 2026-11-22T10:59:10+01:00 |
| S31 | Paramètres déclarés dans le code | `grep -rn 'declare_parameter\|get_parameter'` | `raw/20261122-105910/static/08_params_py.txt` | 2026-11-22T10:59:10+01:00 |
| S32 | Diffuseurs et écouteurs TF dans le code | `grep -rn 'TransformBroadcaster\|lookup_transform\|Buffer\('` | `raw/20261122-105910/static/08_tf_py.txt` | 2026-11-22T10:59:10+01:00 |
| S33 | Appels bloquants candidats dans le code | `grep -rn 'time\.sleep\|\.result()\|cv2\.imshow\|requests\.\|subprocess\.\|spin_once'` | `raw/20261122-105910/static/08_sleeps_py.txt` | 2026-11-22T10:59:10+01:00 |
| S34 | Unités en échec sur le poste | `systemctl --failed` | `raw/20261122-105910/runtime/19_units_failed.txt` | 2026-11-22T11:06:55+01:00 |
| S35 | Contexte de la collecte statique (HEAD git, branche, fichiers modifiés) | `git rev-parse HEAD`, `git status --porcelain` | `raw/20261122-105910/static/00_meta.txt` | 2026-11-22T10:59:10+01:00 |
| S36 | Liste des fichiers YAML du workspace | `find . -name '*.yaml'` | `raw/20261122-105910/static/05_yaml_fichiers.txt` | 2026-11-22T10:59:10+01:00 |
| S37 | Enveloppe de repos du bras validée par l'opérateur | copie de `config/preconditions.yaml` | `raw/20261122-105910/sources/preconditions.yaml` | 2026-11-22T11:08:00+01:00 |
| S38 | Contrat du service du directeur | copie de `clawbot_interfaces/srv/DirectorCommand.srv` | `raw/20261122-105910/sources/DirectorCommand.srv` | 2026-11-22T11:08:00+01:00 |
| S39 | Configuration de l'EKF | copie de `config/ekf.yaml` | `raw/20261122-105910/sources/ekf.yaml` | 2026-11-22T11:08:00+01:00 |
| S40 | Profil Fast DDS du dépôt | copie de `fastdds_profile.xml` | `raw/20261122-105910/sources/fastdds_profile.xml` | 2026-11-22T11:08:00+01:00 |
| S42 | Résultat du point d'entrée de test officiel | `scripts/run_tests.sh tests` | `raw/20261122-105910/runtime/21_tests_run_tests_sh.log` | 2026-11-22T11:22:10+01:00 |
| S43 | Résultat de la suite complète hors deux scripts non-pytest | `ROS_DOMAIN_ID=98 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests -q --ignore=tests/test_cpp_bridge.py --ignore=tests/test_modes.py` | `raw/20261122-105910/runtime/22_tests_suite_complete.log` | 2026-11-22T11:23:05+01:00 |
| S44 | Résultat d'un test unitaire ciblé | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_ekf_config.py -q` | `raw/20261122-105910/runtime/23_test_ekf_config.log` | 2026-11-22T11:24:30+01:00 |
| S45 | Code de l'arbitre de sécurité (copie à l'instant de la collecte) | copie de `clawbot_safety/clawbot_safety/arbitrator.py` | `raw/20261122-105910/sources/arbitrator.py` | 2026-11-22T11:25:00+01:00 |
| S46 | Seuils de l'arbitre (copie) | copie de `clawbot_safety/clawbot_safety/thresholds.py` | `raw/20261122-105910/sources/thresholds.py` | 2026-11-22T11:25:00+01:00 |
| S47 | Rejeu partiel de la collecte dynamique (nœuds, topics, unités en échec) | `ros2 node list`, `ros2 topic list -t`, `systemctl --failed` | `raw/20261122-111310/runtime/01_nodes.txt` | 2026-11-22T11:13:10+01:00 |

## 4. Zones non observées

- **Latence bout-en-bout de chaque chaîne** — aucun message ne porte d'horodatage de bout en bout comparable, et aucun outil de traçage n'est installé. `[NON OBSERVÉ / À VÉRIFIER]` → obtenir : `ros2 topic delay /cmd_vel` (exige un `header` renseigné par l'émetteur, donc une modification de code) ou `ros2_tracing` / `perf` (installation = action mutante, hors périmètre).
- **Ventilation CPU par callback et par thread** — `ps` ne donne que la moyenne par processus. `[NON OBSERVÉ / À VÉRIFIER]` → obtenir : `ros2 run --prefix 'perf record -g' …` ou `py-spy dump --pid <pid>` (outil absent, installation hors périmètre).
- **Profondeur de file (`History (Depth)`) des endpoints actifs** — `ros2 topic info -v` renvoie `UNKNOWN` pour tous les endpoints (S07). `[NON OBSERVÉ / À VÉRIFIER]` → obtenir : lecture du code (`create_publisher`/`create_subscription` et profils QoS, cf. S29) ou `ros2 param get` sur les nœuds C++ qui exposent `qos_overrides`.
- **Firmware et version du MCU** — le protocole série n'expose pas la version dans le graphe. `[NON OBSERVÉ / À VÉRIFIER]` → obtenir : lecture directe de la carte avec `Rosmaster_Lib` (impose l'arrêt de `ros2-driver-node.service`, donc action mutante hors périmètre de cette collecte).
- **Identité USB des capteurs (`VID:PID`, chemins `by-id`)** — non relevée dans cette collecte. `[NON OBSERVÉ / À VÉRIFIER]` → obtenir : `udevadm info -q property -n /dev/video0` et `ls -l /dev/serial/by-id/`.
- **Consommation électrique par nœud** — `tegrastats` donne la puissance totale (`VDD_IN`), pas la répartition. `[NON OBSERVÉ / À VÉRIFIER]` → obtenir : mesure externe (pince ampèremétrique) ou `INA3221` si exposé sur ce port.
- **Comportement sous charge réseau dégradée** — non testé (un test de perte Wi-Fi perturberait le robot en production). `[NON OBSERVÉ / À VÉRIFIER]` → obtenir : `tc qdisc add dev wlP1p1s0 root netem loss 5%` en domaine 99 sur poste isolé, jamais sur le domaine 28.
