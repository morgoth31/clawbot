# Audit de robustesse, déploiement et maintenabilité — Clawbot X3

## 1. Résilience et supervision

### 1.1 Politique de redémarrage des unités

14 unités actives inspectées [S25], 73 fichiers `.service` sur le poste.

| Unité | `Restart` | `RestartSec` | `Requires` | `Conflicts` | `ExecStop` | Source |
|---|---|---|---|---|---|---|
| `clawbot-director.service` | **always** | non renseigné | `clawbot-safety-arbitrator` | `shutdown.target` | **oui** (`scripts/annuler_tache_service.sh`) | [S25] |
| `clawbot-safety-arbitrator.service` | **always** | non renseigné | `ros2-driver-node` | `shutdown.target` | non | [S25] |
| `clawbot-sentinel.service` | **always** | non renseigné | `clawbot-director` | `shutdown.target` | non | [S25] |
| `ros2-driver-node.service` | on-failure | non renseigné | `ros2-hardware-service` | `shutdown.target` | non | [S25] |
| `ros2-hardware-service.service` | on-failure | non renseigné | — | `shutdown.target` | non | [S25] |
| `ros2-llm-bridge-cpp.service` | on-failure | non renseigné | `ros2-hardware-service` | `shutdown.target` | non | [S25] |
| `clawbot-ekf.service` | on-failure | non renseigné | `ros2-driver-node` | `shutdown.target` | non | [S25] |
| `clawbot-lidar.service` | on-failure | non renseigné | — | `shutdown.target` | non | [S25] |
| `clawbot-slam.service` | on-failure | non renseigné | `ros2-driver-node` | **`clawbot-nav2`** | non | [S25] |
| `clawbot-wrist-camera.service` | on-failure | non renseigné | — | `shutdown.target` | non | [S25] |
| `clawbot-description.service` | on-failure | non renseigné | — | `shutdown.target` | non | [S25] |
| `yolo-inference.service` | on-failure | non renseigné | — | `shutdown.target` | non | [S25] |
| `yahboom_oled.service` | **no** | — | — | `shutdown.target` | non | [S25] |
| `clawbot-docs.service` | on-failure | non renseigné | — | `shutdown.target` | non | [S25] |

Constats :

1. **`RestartSec` n'est renseigné nulle part** : systemd applique son défaut de 100 ms. Un service qui échoue au démarrage (port occupé, périphérique absent) est donc relancé en rafale.
2. **`Restart=always` sur trois unités qui ne sont pas des démons de calcul** : `director`, `safety_arbitrator`, `sentinel` redémarrent même après un arrêt volontaire, ce qui interdit un arrêt propre sans `systemctl stop` explicite et masque les sorties normales.
3. **Un seul `ExecStop`** : arrêter les autres unités laisse les nœuds sans étape de nettoyage (aucune annulation de tâche, aucune remise à zéro de la pince).
4. **`clawbot-slam` et `clawbot-nav2` sont mutuellement exclusifs** : c'est la seule protection contre deux écrivains de `map → odom` [S25].
5. **Le cycle de vie ROS 2 n'est pas utilisé** : 0 occurrence de `LifecycleNode` dans les 27 launch files du dépôt [S23]. Seul `ydlidar_ros2_driver_node` expose un service `change_state` et publie `/ydlidar_ros2_driver_node/transition_event` [S04], [S03] — mais son lancement est statique.

### 1.2 Arrêt et faux échec

`clawbot-sentinel` a été arrêté le 2026-11-22 à 10:14:06 et a quitté avec `rclpy.executors.ExternalShutdownException` et `status=1/FAILURE` [S19] :

```
Nov 22 10:14:06 bash[1354]:   File ".../rclpy/executors.py", line 649, in _wait_for_ready_callbacks
Nov 22 10:14:06 bash[1354]:     raise ExternalShutdownException()
Nov 22 10:14:06 bash[1354]: rclpy.executors.ExternalShutdownException
Nov 22 10:14:06 systemd[1]: clawbot-sentinel.service: Main process exited, code=exited, status=1/FAILURE
```

L'exception est levée par `rclpy.spin` sur un `SIGTERM` : c'est un **arrêt normal qui produit un échec d'unité**. Conséquence : l'unité reste en `failed`, doit être remise à zéro par `systemctl reset-failed` avant de repartir, et toute supervision qui compte les unités en échec compte un faux positif [S19].

### 1.3 Supervision

| Mécanisme | Existence | Preuve |
|---|---|---|
| `/diagnostics` publié | oui, par `ekf_filter_node` seul, à 1,936 Hz | [S02], [S08] |
| `/diagnostics` consommé | **non : 0 abonné** | [S07] |
| `diagnostic_aggregator` | absent du graphe | [S01] |
| Chien de garde applicatif | `WATCHDOG_PERIOD_S = 0.1` (directeur), `CMD_TIMEOUT_S = 0.5` et `STALE_S = 2.0` (arbitre), `MOTION_WATCHDOG_S=1.5` (service matériel, variable d'environnement) | [S28], [S46], [S25] |
| Surveillance de flux capteur | `sentinel` sonde toutes les 1,0 s (`PERIODE_SONDE_S`) | [S28] |
| Supervision de latence | aucune | — |
| Supervision thermique | aucune | — |

**Le système publie un diagnostic que personne ne lit.** `ekf_filter_node` produit `/diagnostics` à 1,9 Hz et aucun nœud n'y est abonné [S07] ; le seul tableau de bord est HTTP (8001, 8000) et n'est pas dans le graphe.

### 1.4 État global du poste

`systemctl --failed` renvoie deux unités, **aucune du robot** : `apport-autoreport.service` et `logrotate.service` [S34]. L'état `degraded` du poste n'est donc pas imputable à la pile ROS, mais il prive l'opérateur d'un signal global fiable : un `systemctl is-system-running` qui répond `degraded` ne dit rien de l'état du robot.

## 2. Points uniques de défaillance

| SPOF | Nature | Effet observable si perte | Détection actuelle | Source |
|---|---|---|---|---|
| Port série du MCU | matériel + logiciel | plus de `/voltage`, `/imu/data_raw`, `/odom_raw`, `/vel_raw`, `/arm/servo_angles` : la base et le bras deviennent aveugles et muets | `Restart=on-failure` sur le pilote, sans `RestartSec` ; aucun message d'erreur normalisé | [S25], [S02] |
| `astra_camera` (couleur + profondeur + IR + points) | processus unique | perte simultanée des quatre flux ; `sentinel` perd son entrée | aucun abonné ne signale l'absence | [S02], [S07] |
| `ydlidar_ros2_driver_node` | matériel USB | plus de `/scan` : l'arbitre perd son entrée d'obstacle | **détecté** : `decide()` renvoie `SENSOR_STALE` et met la consigne à zéro dès que `age_scan` dépasse `STALE_S = 2.0 s` ; l'état est publié sur `/safety/state` | [S45], [S46] |
| Wi-Fi `wlP1p1s0` | réseau | seule interface montée : la découverte DDS et tout le trafic image passent par elle | aucune | [S15] |
| `ros2-hardware-service` | logiciel | il détient `/cmd_vel`, `/servo_ctrl`, `/Buzzer`, `/RGBLight` : perte du contrôle direct ET de l'API HTTP 8001 | `Restart=on-failure` | [S02], [S25] |
| `director` | logiciel | plus de décision ; `sentinel` perd son interlocuteur | `Restart=always` | [S25] |
| Carte de commande (alimentation des servos) | matériel | bras immobile, angles relus figés à la dernière valeur | aucune | [S02] |
| Disque à 84 % | infrastructure | plus d'installation, de sacs, de journaux ; un `logrotate` déjà en échec | `logrotate.service` en échec sur le poste | [S13], [S34] |
| `clawbot-docs.service` | logiciel | documentation indisponible, sans effet sur le robot | `Restart=on-failure` | [S25] |

Deux SPOF sont **silencieux** : ni `astra_camera` ni `ydlidar` n'ont de consommateur qui signale l'absence de flux. La seule détection possible aujourd'hui est un `ros2 topic hz` manuel.

## 3. Gestion des erreurs

| Indicateur | Valeur mesurée | Source |
|---|---|---|
| Blocs `except` dans les nœuds maison (`director`, `safety`, `sentinel`, `hardware_service`) | 38 | comptage sur l'arbre, 2026-11-22T11:20 |
| Dont `except Exception: pass` consécutifs | 4 | `grep -A1 except \| grep -c pass` |
| Valeurs sentinelles `-1` sur `/arm/servo_angles` | documentées par la base OKF ; non re-mesurées ici | `[NON OBSERVÉ / À VÉRIFIER]` → obtenir : `ros2 topic echo /arm/servo_angles --once` après arrêt de la carte |
| Sorties de processus par motif | `subprocess.check_output(['pgrep','-f','slam_launch.py'])` et `subprocess.run(['pkill','-9','-f',node])` dans le service matériel | [S33] |

Trois faits qui pèsent :

1. **`pkill -9 -f <motif>` depuis un nœud** [S33] : le motif cherche dans la ligne de commande complète ; un opérateur qui a la même chaîne dans son shell est tué avec la cible. C'est aussi la raison pour laquelle aucune commande de ce dossier n'utilise `pkill -f`.
2. **Le directeur dégrade proprement** : quand un serveur d'action est absent, il avance l'étape en échec avec le motif `action indisponible : <nom>` ([S30], code) — comportement correct, mais qui rend une unité arrêtée indiscernable d'une panne applicative pour l'appelant HTTP.
3. **Aucun message d'erreur normalisé** : les échecs se lisent dans `/director/state` (JSON), `/safety/state` (chaîne), `/sentinel/event` (JSON) et les journaux systemd, avec trois formats différents [S02].

## 4. Maintenabilité

| Constat | Valeur mesurée | Effet | Source |
|---|---|---|---|
| Paquets sur disque | 38, dont 8 paquets de didacticiel (`pkg_*`) et 12 paquets vendor non déployés | la moitié de l'arbre n'est pas du code du robot | [S21] |
| Driver châssis | 2 copies identiques (`clawbot/…` et `yahboomcar_ws/src/…`) | toute correction doit être appliquée deux fois ; la copie déployée est la seconde | `diff -q`, 2026-11-22T11:10 |
| Serveur API | 3 fichiers `api_server.py` dans `ros2_llm_bridge*` | trois variantes d'une même interface HTTP | [S28] |
| Plus gros fichiers | `ros2_llm_bridge/hardware_service.py` 979 lignes, `bridge_mcp/health.py` 826, `yolo_service.py` 415 | concentration de responsabilités : HTTP + ROS + série + processus | `wc -l`, 2026-11-22T11:12 |
| Répertoire `install/` imbriqué | `ros2_llm_bridge/install/` versionné ? non ignoré par le `.gitignore` racine (seul `/install` l'est) | confusion entre source et artefact de build | `.gitignore`, [S36] |
| Launch files | 27, dont 0 composition, 0 cycle de vie ; le lancement réel est fait par 14 unités | deux descriptions concurrentes du démarrage | [S23], [S25] |
| Configuration | 5 nœuds maison à 1 paramètre (`use_sim_time`) | aucun réglage sans redémarrage | [S06] |
| YAML source vs installé | 2 copies par paquet (`config/` et `install/<pkg>/share/…`), `sha256` relevés | modifier la source ne change pas le service | [S36], [S25] |
| Unités systemd | fichiers du dépôt liés dans `/etc/systemd/system` | modifier l'unité casse le lien si on écrit dans `/etc` | [S26] |
| Interface du directeur | service JSON opaque (`request_json`/`response_json`) | aucun contrat lisible par un tiers, aucune génération de client | [S38] |

Le point le plus coûteux pour une reprise : **le démarrage est décrit deux fois** (27 launch files + 14 unités) et **le code est dupliqué deux fois** (driver, API). Un nouveau venu qui modifie `clawbot/yahboomcar_bringup/` ne change rien à ce qui tourne [S25].

## 5. Testabilité

| Suite | Chemin | Commande | Résultat observé | Source |
|---|---|---|---|---|
| Entrée officielle | `scripts/run_tests.sh` | `scripts/run_tests.sh tests` | **exit 2**, collecte interrompue : 2 erreurs (`tests/test_cpp_bridge.py`, `tests/test_modes.py` appellent `http://localhost:8002` à l'import) | [S42] |
| Suite sans ces deux fichiers | `tests/` | `ROS_DOMAIN_ID=98 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests -q --ignore=…` | **238 passed, 1 skipped, 19 errors en 48,52 s** (les 19 erreurs viennent de `tests/test_regression.py`, dont les signatures sont interprétées comme des fixtures) | [S43] |
| Test unitaire ciblé | `tests/test_ekf_config.py` | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_ekf_config.py -q` | **3 passed en 0,07 s** | [S44] |
| Banc de nœud isolé | `clawbot_*/test/` | lancé par la suite ci-dessus | inclus dans les 238 | — |
| Simulation | `preuve_navigation_99.py`, domaine 99 | `[NON OBSERVÉ / À VÉRIFIER]` → obtenir : `ROS_DOMAIN_ID=99 python3 scripts/preuve_navigation_99.py` (non lancé : hors périmètre d'un audit en lecture seule, et long) | — | — |

Deux défauts de testabilité établis :

1. **Le point d'entrée documenté ne rend pas de résultat exploitable** : `scripts/run_tests.sh tests` s'arrête avant exécution, sur deux fichiers qui ne sont pas des tests pytest [S42]. Un opérateur qui lance la commande annoncée conclut à un dépôt cassé.
2. **19 tests sur 257 sont en erreur de collecte** (`test_regression.py`) : ils sont écrits avec un paramètre positionnel que pytest prend pour une fixture. Le taux de réussite réel est donc 238/257, et la suite n'est pas verte.

Aucun test ne couvre : le contrat HTTP 8000/8001/8003, l'absence de flux capteur, la chaîne `cmd_vel → cmd_vel_safe → série`, ni les QoS.

## 6. Registre des risques

### Criticité haute

| ID | Risque | Classe | Preuve | Impact exploitable | Mitigation proposée |
|---|---|---|---|---|---|
| R01 | Le flux de profondeur ne produit rien alors que son producteur consomme 57 % du CPU | performance + fonctionnel | 0 message en 12 s sur `/camera/depth/image_raw` et `/camera/depth/points` ; 57,2 % de CPU [S09], [S12] | toute perception de profondeur est morte ; `sentinel` est aveugle à sa seconde entrée | instrumenter le driver Astra (mode vidéo, `depth_fps`), ou couper la profondeur et l'assumer explicitement |
| R02 | La détection d'objets n'existe pas dans le graphe | fonctionnel | `/detections` et `/camera/detection_image` sans éditeur [S07] | deux abonnés attendent des messages qui ne viendront jamais | republier le résultat d'inférence en ROS 2, ou supprimer les abonnés |
| R03 | Le bras n'est ni planifiable ni commandable | fonctionnel | aucune action, `clawbot-arm-controller` et `move-group` non actifs [S05], [S25] | le directeur échoue à toute étape de bras ; l'opérateur ne peut pas déplacer le bras par MoveIt | activer et superviser les deux unités, ou déclarer la capacité indisponible au niveau de l'API |
| R04 | L'arbitre de sécurité est mono-thread et sans priorité | sécurité + temps réel | 1 thread, ~50 msg/s en entrée, 20 Hz en sortie, 0 `Nice=`/`CPUAffinity=` [S28], [S25] | un callback lent retarde l'arrêt ; `astra_camera` à 57 % concourt sur les mêmes cœurs | executor multi-thread avec groupes dédiés, priorité d'ordonnancement sur le nœud d'arrêt |
| R05 | Un arrêt normal produit un `failed` d'unité | exploitation | `ExternalShutdownException` → `status=1/FAILURE` [S19] | faux positif de supervision, unité bloquée jusqu'à `reset-failed` | attraper l'exception dans `main()` et sortir 0, comme le fait déjà le directeur |

### Criticité moyenne

| ID | Risque | Classe | Preuve | Impact exploitable | Mitigation proposée |
|---|---|---|---|---|---|
| R06 | Tout le trafic DDS passe par le Wi-Fi | infrastructure | `wlP1p1s0` seule interface montée, `eno1` sans porteuse [S15] | latence et pertes non bornées sur les images et le nuage de points | transport SHM/UDP local pour les flux volumineux, ou lien filaire |
| R07 | Les cinq nœuds de décision ne sont pas paramétrables | maintenabilité | 1 paramètre par nœud (`use_sim_time`) [S06] | aucun réglage sans redémarrage, aucune reconfiguration en mission | exposer seuils et cadences en paramètres ROS 2 |
| R08 | Aucune mesure de latence ni d'horodatage | observabilité | aucun `header.stamp` dans les publications maison [S30] | aucune régression de performance ne peut être détectée | horodater entrées/sorties, publier un écart mesuré |
| R09 | `/diagnostics` n'a aucun consommateur | observabilité | 1 éditeur, 0 abonné [S07] | les défauts EKF ne remontent nulle part | `diagnostic_aggregator` + remontée dans `/director/state` |
| R10 | Deux copies du driver et trois du serveur API | maintenabilité | `diff -q` identique sur deux chemins ; 3 `api_server.py` [S28] | correction appliquée au mauvais endroit, sans effet | une seule source, vendor en dépendance externe |
| R11 | `RestartSec` absent sur 14 unités, `Restart=always` sur trois | exploitation | [S25] | rafales de redémarrage ; arrêt volontaire impossible sans `stop` | `RestartSec=2`, `Restart=on-failure` partout sauf nécessité démontrée |
| R12 | Le point d'entrée des tests échoue à la collecte | testabilité | `scripts/run_tests.sh tests` → exit 2 | aucune vérification reproductible n'est lancée par défaut | exclure les deux scripts non-pytest dans le script |

### Criticité basse

| ID | Risque | Classe | Preuve | Impact exploitable | Mitigation proposée |
|---|---|---|---|---|---|
| R13 | Disque à 84 %, `logrotate` en échec | infrastructure | 117/147 Go, `logrotate.service` failed [S13], [S34] | installation et enregistrement de sacs impossibles | purge des journaux et des artefacts de build |
| R14 | L'afficheur OLED consomme 9 % de CPU | performance | 19 Mo, 9,0 % [S12] | charge inutile sur un cœur | réduire la cadence ou déporter l'affichage |
| R15 | 8 paquets de didacticiel dans l'arbre | maintenabilité | [S21] | bruit dans les builds et les recherches | déplacer hors du workspace déployé |
| R16 | La documentation est servie en mode développement sur `0.0.0.0:8080` | sécurité | `mkdocs serve --dev-addr 0.0.0.0:8080` [S25] | serveur de développement exposé, sans authentification | servir un site statique, ou restreindre à `127.0.0.1` |
| R17 | Aucun cycle de vie ROS 2 | architecture | 0 `LifecycleNode` sur 27 launch files [S23] | pas d'état « inactif/actif » par nœud, pas de démarrage ordonné | introduire des nœuds à cycle de vie sur les composants critiques |
