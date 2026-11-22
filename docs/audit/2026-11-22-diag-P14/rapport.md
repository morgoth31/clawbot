# Diagnostic après P14 — rapport

## 1. État en trois lignes

Le robot est **opérationnel au sens du contrôle de fumée** : `smoke_check.sh` sort 0 et les huit cadences de référence sont tenues (§6, D34). **Aucun test n'échoue** : `check.sh`, `check.sh --strict-duplicates`, `--integration` et la suite complète sortent 0 (776 passés, 14 ignorés, D10-D13). **Le déploiement de P14 n'est pas fait** : `clawbot.target` est absente de `/etc`, la cible est `inactive`, le Jetson n'a pas redémarré depuis le 2026-11-15 (D30, D32) — en revanche la construction **propre** échoue sur un paquet (D20, §5).

Le défaut à corriger en premier n'est donc pas un test rouge : c'est `ros2_llm_bridge_cpp`, qui ne se construit plus de zéro depuis P14.

## 2. Prompts P00 à P14

`git branch --merged main` ne renvoie **que `main`** (D01) : aucune branche de prompt n'est fusionnée dans `main`, dont la tête est `7344951`. Toutes sont en revanche contenues dans la branche courante `refactor/REQ-OPS-040-demarrage` (`git merge-base --is-ancestor`), donc le travail est présent dans l'arbre de travail mais **absent de `main`**.

| Prompt | Branche | Fusionné dans main | Commit de fusion | Rapport de fin | Remarque |
|---|---|---|---|---|---|
| P00 | `feat/REQ-TEST-001-cadre` | non | aucun | `deploy/journal/2026-11-22_p00*` : absent | tête `972b7cc`, contenue dans HEAD |
| P01 | `docs/REQ-OPS-001-mesures` | non | aucun | `2026-11-22_p01*` : absent (mesures dans `docs/audit/`) | tête `a81482e` |
| P02 | `fix/REQ-OPS-010-systemd` | non | aucun | `2026-11-22_p02_unites.md` | tête `e416bcd` |
| P03 | `feat/REQ-DRV-001-pilote` | non | aucun | `2026-11-22_p03_pilote.md` | tête `5a8eac9` |
| P04 | `feat/REQ-SAFETY-010-multiplexeur` | non | aucun | `2026-11-22_p04_rapport.md` | tête `a1dae5f` |
| P05 | `feat/REQ-HEALTH-001-moniteur` | non | aucun | `2026-11-22_p05_rapport.md` | tête `994ec45` |
| P06 | `feat/REQ-ARCH-010-interfaces` | non | aucun | `2026-11-22_p06_rapport.md` | tête `57f55a7` |
| P07 | `feat/REQ-CAPA-001-gestionnaire` | non | aucun | `2026-11-22_p07_rapport.md` | tête `851e51d` |
| P08 | `feat/REQ-EXEC-001-skills` | non | aucun | `2026-11-22_p08_rapport.md` | tête `1fe7275` |
| P09 | **absente** | non | aucun | `2026-11-22_p09_rapport.md` | aucun branche dédiée ; commits sur `feat/REQ-EXEC-001-skills` |
| P10 | **absente** | non | aucun | `2026-11-22_p10_rapport.md` | idem |
| P11 | `fix/REQ-PERC-001-astra` | non | aucun | `2026-11-22_p11_rapport.md` | tête `d0b71f7` |
| P12 | `feat/REQ-PERC-010-detection` | non | aucun | `2026-11-22_p12_rapport.md` | tête `9168970` |
| P13 | `feat/REQ-ARM-001-bras` | non | aucun | `2026-11-22_p13_rapport.md` | tête `1111bee` = base de P14 |
| P14 | `refactor/REQ-OPS-040-demarrage` | non | aucun | `2026-11-22_p14_rapport.md` | tête `2c2d1d7`, branche courante |

## 3. Tests en échec

**Aucun test n'échoue.** Les cinq exécutions demandées sortent toutes 0 :

| Exécution | Domaine | Résultat | Code | Artefact |
|---|---|---|---|---|
| `scripts/check.sh` | 98 | 776 passés, 14 ignorés | 0 | D10 |
| `scripts/check.sh --strict-duplicates` | 98 | idem, doublons conformes | 0 | D11 |
| `scripts/check.sh --integration` | 99 | 83 passés, 1 ignoré | 0 | D12 |
| `pytest -q -rfEs --tb=long` | 98 | 776 passés, 14 ignorés | 0 | D13 |
| `pytest --collect-only -q` | 98 | 777 collectés, 0 erreur | 0 | D15 |

| nodeid | REQ | type | première ligne de l'erreur | fichier:ligne | stable/instable (D16) | passait avant P14 (D17) |
|---|---|---|---|---|---|---|
| — | — | — | aucun test en échec, aucune erreur de collecte | — | sans objet | sans objet |

Le seul échec de la session est **hors pytest** : la construction propre (D20). Voir §5.

## 4. Tests modifiés depuis P13

Base : `1111bee`. Onze fichiers de test/configuration de test modifiés ou ajoutés (D05, D05b). Par ordre d'importance décroissante — **rien n'a été affaibli au sens « faire passer un test rouge »** : aucun `skip`, aucun `xfail`, aucune tolérance élargie, `.untraced_baseline` inchangé (diff vide). Deux réductions de périmètre sont en revanche réelles et listées en tête.

1. **`pytest.ini` — réduction de périmètre réelle.** `norecursedirs` gagne `attic`. Effet mesuré : la suite passe de **816 à 776 tests collectés** (−40). Ce sont les tests `test_flake8.py` / `test_copyright.py` / `test_pep257.py` des 14 paquets vendor archivés, plus `tests/test_servo_round_robin.py` et `tests/test_cmd_vel_scaling.py` déplacés sous `attic/`. Aucune assertion du code vivant n'est touchée ; le lint est fait par ruff, mais `check.sh` note `ruff absent` depuis le début de la session.
2. **`tests/test_units.py` — réduction de périmètre partielle.** `UNITES_ROBOT` est scindé en `UNITES_ACTIVES` + `UNITES_HORS_LIEN` + `UNITES_A_LA_DEMANDE` ; la politique standard (`RestartSec=2`, `TimeoutStopSec=10`) n'est plus vérifiée que sur `UNITES_POLITIQUE` (18 unités) et les 8 unités à la demande passent par un tableau `EXCEPTIONS` qui vérifie leurs valeurs déclarées. Les unités concernées sont donc toujours vérifiées, chacune contre ses valeurs propres.
3. `clawbot_safety/test/test_arbitre_parametres.py` — 2 assertions supprimées (`inputs.legacy.topic == "/cmd_vel"`, `priority == 10`), remplacées par une assertion **plus stricte** sur la liste exacte `inputs.names == [teleop, nav, skill]` et `"legacy" not in params["inputs"]`. Cohérent avec REQ-OPS-044, approuvée.
4. `clawbot_safety/test/test_arbitre_multiplexeur.py` — `ENTREES` perd `legacy` : les couples de priorité testés passent de 6 à 3. Conséquence mécanique du retrait de l'entrée.
5. `tests/test_camera_poignet.py` — 5 assertions changent de **source**, pas de propriété : `UNIT_CAMERA`/`UNIT_YOLO` lisent les fichiers de lancement (`clawbot_bringup/launch/…`) ; `camera_frame_id:=X` → `"camera_frame_id": "X"` ; `output_encoding:=yuv422_yuy2` → même forme dict ; `__ns:=/wrist_camera` → `namespace="wrist_camera"` ; `Environment=ROS_DOMAIN_ID=28` → `ROS_DOMAIN_ID=28` dans `deploy/env/clawbot.env` (une assertion lit désormais l'unité pour `User=jetson`).
6. `tests/test_arm_joint_sources.py` — chemin `launch/robot_description.launch.py` → `clawbot_bringup/launch/description.launch.py` ; assertions sur quotes simples → forme `dict` (`source_list=["/arm/joint_states"]`, `rate=20.0`), et `executable='…'` → `executable="…"`.
7. `tests/test_p07_delegation.py`, `tests/test_p11_astra.py` — `ros2_llm_bridge/hardware_service.py` → `clawbot_bringup/clawbot_bringup/hardware_service.py` (déplacement P14).
8. `clawbot_director/test/test_nav2_config.py` — `launch/navigation.launch.py` → `clawbot_bringup/launch/navigation.launch.py`.
9. `tests/test_p14_demarrage.py` — **nouveau**, 11 tests (REQ-OPS-040 à 045, REQ-NET-001).
10. `requirements/OPS.yaml` — REQ-OPS-040 à 045 ajoutées ; `requirements/NET.yaml` — REQ-NET-001.
11. `requirements/ARM.yaml` — REQ-ARM-003 et REQ-ARM-004 passent `draft` → `approved`, `approved_by: "opérateur 2026-11-22"`, avec `approval_note` citant la réponse de l'opérateur. Effet : ce sont ces deux entrées qui bloquaient la trace avant P14 (voir `D10` du run antérieur `/tmp/p14_check3.log`).

## 5. Construction

**La construction propre échoue** (D20, D20b) :

```
Failed   <<< ros2_llm_bridge_cpp [10.3s, exited with code 1]
Aborted  <<< yahboomcar_description, yolo_node, clawbot_interfaces
Summary: 1 package failed, 3 packages aborted, 7 packages not processed
```

Erreur exacte :

```
CMake Error at CMakeLists.txt:18 (find_package):
  By not providing "Findclawbot_interfaces.cmake" in CMAKE_MODULE_PATH this project
  has asked CMake to find a package configuration file provided by "clawbot_interfaces",
  but CMake did not find one.
```

Cause factuelle : `ros2_llm_bridge_cpp/CMakeLists.txt:18` appelle `find_package(clawbot_interfaces REQUIRED)` (ajouté pendant P14 pour l'action `/clawbot/execute_skill`), mais `ros2_llm_bridge_cpp/package.xml` **ne déclare aucune dépendance envers `clawbot_interfaces`** (`grep clawbot_interfaces package.xml` → 0 occurrence). Colcon construit donc les deux paquets en parallèle et l'API configure avant que les interfaces soient installées. Les trois paquets « aborted » ne sont pas fautifs : reconstruits seuls, ils passent (`D20b`, `Summary: 3 packages finished`, EXIT=0).

Pourquoi cela n'apparaissait pas plus tôt : le dernier `colcon build` du paquet a été fait avec `install/setup.bash` sourcé, où `clawbot_interfaces` était déjà installé (fichier `install/clawbot_interfaces/share/clawbot_interfaces/cmake/`). Un build incrémental dans un espace déjà peuplé masque la dépendance manquante.

Références vers `attic/` (D21) : **aucune**. Les 12 paquets archivés cités par un fichier vivant ne le sont que par `tests/test_p14_demarrage.py:43`, qui porte la liste attendue des paquets archivés. Aucun `import`, aucun `ExecStart`, aucun chemin de lancement ne pointe vers `attic/`.

## 6. Robot (domaine 28, lecture seule)

| Mesure | Résultat | Artefact |
|---|---|---|
| Unités robot actives | **17** (`active running`), dont `clawbot-docs`, `clawbot-slam`, `clawbot-yolo`, `ros2-llm-bridge-cpp`, `yahboom_oled` | D30 |
| `clawbot.target` | **inactive**, et **absente de `/etc/systemd/system/`** | D30, D31 |
| Unités en échec | **aucune unité du robot** ; seul `apport-autoreport.service` (système) | D30 |
| `clawbot-mission-executive` | **inactive** depuis le 2026-11-22 18:49:38 — `Job … start failed with result 'dependency'` ; `Requires=clawbot-skill-server.service` | D31, D31b |
| `smoke_check.sh` | **conforme, code 0** ; `/scan` 10,123 Hz, `/imu` 10,004, `/joint_states` 20,001, `/director/state` 5,000, `/cmd_vel_safe` 19,999, `/safety/state` 19,999, `/voltage` 9,997, `/odom` 9,999 | D34 |
| `/cmd_vel` | **1 éditeur : `llm_bridge_node`** (ancien code déployé), 1 abonné `safety_arbitrator` | D35 |
| `/cmd_vel_safe` | 1 éditeur (`safety_arbitrator`) | D34, D35 |
| Nœuds | **23** au total ; **17 applicatifs** après retrait des 2 `transform_listener_impl_*`, du `launch_ros_*` et des 3 nœuds rosbridge (`rosapi`, `rosapi_params`, `rosbridge_websocket`) | D35 |
| `inputs.names` de l'arbitre | `['teleop', 'nav', 'skill', 'legacy']` — l'entrée `legacy` est **encore chargée** | D35 |
| Écoute réseau | `9090` (rosbridge) sur **0.0.0.0** et `[::]`, `8000` (api_server) sur 0.0.0.0, `8001`, `8003` sur 0.0.0.0, `8080` (mkdocs) sur **127.0.0.1** | D35 |
| Capacités | `base`, `lidar`, `wrist_vision`, `detection` = ACTIVE ; `mapping`, `navigation`, `arm`, `depth_vision`, `voice` = INACTIVE | D33b/10 |
| Santé | `safety_state: OK`, `estop_latched: false`, `voltage: 11,90 V`, `stale_flows: []` | D33b/11 |
| Démarrage | `uptime -s` = **2026-11-15 12:02:56** : aucun redémarrage depuis six jours | D32 |

## 7. Écarts avec P14

| Demandé par P14 | État | Preuve |
|---|---|---|
| Unités réécrites vers `ros2 launch clawbot_bringup` | **fait dans le dépôt**, non déployé : `/etc` porte encore les anciens `ExecStart` | D30, D31 |
| `clawbot.target` comme point d'entrée | **écrit dans `services/`, absent de `/etc`**, cible inactive | D31 |
| `ROS_DOMAIN_ID` dans un `EnvironmentFile=` unique | écrit (`deploy/env/clawbot.env`), non déployé : l'arbitre charge encore la table à 4 entrées de l'ancienne installation | D35 |
| API 8000 sans éditeur de vitesse, branchée sur l'exécutif | **fait dans le code, non construit ni déployé** : `llm_bridge_node` publie toujours `/cmd_vel` | D35 |
| Entrée `legacy` retirée de l'arbitre | **faite dans le dépôt**, encore chargée au runtime | D35 |
| rosbridge retiré ou lié à 127.0.0.1 | unité supprimée du dépôt, **le service tourne encore** et écoute sur 0.0.0.0:9090 | D35 |
| Documentation statique sur 127.0.0.1 | unité réécrite, **`mkdocs serve` toujours en cours** (port déjà lié à 127.0.0.1) | D35 |
| Sentinel simplifié (§5.8), `bridge_mcp` supprimé | **non faits**, déclarés tels quels dans le rapport P14 | D40 §7 |
| Mesure O09 (temps jusqu'au premier `/safety/state`) | **non mesurée** : exige un redémarrage | D32 |
| Nœuds applicatifs ≤ 15 (O11) | **17 aujourd'hui**, 14 attendus après retrait des 3 nœuds rosbridge | D35 |

## 8. Hypothèses (au plus 5)

1. **Le déploiement P14 échouerait à l'étape construction, avant toute bascule.** Fait qui soutient : D20, `Failed <<< ros2_llm_bridge_cpp` sur `find_package(clawbot_interfaces)` absent de `package.xml`. Commande qui tranche : `rm -rf /tmp/b && colcon build --packages-select clawbot_interfaces ros2_llm_bridge_cpp --build-base /tmp/b` dans un shell **sans** `install/setup.bash` — échoue encore.
2. **Aucune mission ne peut être exécutée aujourd'hui.** Fait : D31b, `clawbot-mission-executive` inactive, `Result=dependency` après l'arrêt de `clawbot-skill-server` le 2026-11-22 à 18:49 ; le `Requires=` n'a pas été rejoué au redémarrage du skill-server. Commande qui tranche : `ros2 action list -t | grep execute_mission` (attendu : absente) et `ros2 service call /clawbot/capabilities/list …` déjà obtenu sans erreur.
3. **L'état « 17 nœuds applicatifs » ne mesure pas P14, mais l'ancien déploiement.** Fait : D35, `rosbridge_websocket`/`rosapi`/`rosapi_params` présents alors que leur unité est supprimée du dépôt, et `inputs.names` contient `legacy`. Commande qui tranche : `systemctl show rosbridge -p FragmentPath --value` (le fichier doit encore exister dans `/etc/systemd/system/`).
4. **La cible `clawbot.target` démarrerait 13 unités dont une seule manque aujourd'hui.** Fait : D30 (12 des 13 `Wants=` sont actives), D42 ; l'absente est `clawbot-mission-executive`. Commande qui tranche : après déploiement, `systemctl list-dependencies clawbot.target --no-pager` puis `systemctl is-active` des 13.
5. **Le snapshot standard du skill de diagnostic est inutilisable en l'état.** Fait : D33, `EXIT=1` et dossier vide ; `bash -x` montre l'arrêt sur `source /opt/ros/humble/setup.bash` sous `set -u` (variable non définie), aucune sortie produite. Commande qui tranche : `bash -x ~/.hermes/skills/clawbot/clawbot-ros2-diagnostics/scripts/snapshot_readonly.sh /tmp/x 2>&1 | tail -5` (même arrêt). Le diagnostic a donc été refait à la main (D33b, 12 fichiers).

## 9. Sécurité — réponses de fin de session

- Ai-je publié dans le domaine 28 ? **Non.** Aucun `ros2 topic pub`, aucun goal d'action ; une seule requête de lecture (`/clawbot/capabilities/list`, D33b/10) et un `ros2 topic echo --once` (D33b/11).
- Ai-je modifié `/etc` ou une unité en service ? **Non.** Aucun `systemctl start|stop|restart|enable|disable|daemon-reload`, aucun retour arrière.
- Ai-je modifié du code, des tests, une configuration ou une unité ? **Non.** Le seul ajout est le dossier `docs/audit/2026-11-22-diag-P14/`.
- Processus laissés ? Aucun (les suites de test et le build se sont terminés ; contrôle en fin de session).
- Aucun secret dans le dossier : masqué en amont (§ livraison). `grep -rniE 'token|password|secret|passwd'` ne renvoie que six occurrences du **nom de test** `test_request_without_token_is_rejected` dans les journaux de pytest — aucune valeur, aucun identifiant. Aucun `EnvironmentFile` hors dépôt n'a été copié.
