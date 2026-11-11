# État du projet Clawbot — reprise de session

**Date** : 2026-11-11, après le lot 5 (navigation sur carte)
**Branche** : `docs/site-okf-merge` ; dernier commit de code avant ce lot `95bd39a`
**Robot** : Clawbot X3 Plus, Jetson Orin NX, ROS 2 Humble, domaine 28

> Ce document est fait pour être lu **au début d'une nouvelle session**, à la place d'un
> historique de conversation. Il dit ce qui marche, ce qui est mesuré, ce qui casse, ce qui
> reste, et dans quel ordre continuer.

---

## 1. Comment reprendre

Ouvrir une nouvelle session et envoyer :

> Lis `/home/jetson/clawbot/docs/ETAT-PROJET.md` et
> `docs/superpowers/specs/2026-11-11-architecture-s1-s2-design.md`, puis reprends au §8
> (prochaines étapes) à la brique 6.

Les briques 1 à 5 sont faites : nœud ROS du directeur, surface MCP, exécution réelle des goals,
sentinel, navigation sur carte avec waypoints fermés. Ne pas les refaire. Ne pas relancer les
diagnostics déjà faits : ils sont tous dans ce document avec leurs chiffres.

**La brique 5 n'est pas close pour autant** : la preuve en simulation est faite (3 waypoints à
0,000 / 0,121 / 0,082 m), l'essai **physique** des trois waypoints reste à faire, robot au sol,
opérateur présent. Protocole au §8, brique 5.

**État du dépôt** : le worktree porte des modifications **antérieures** non commitées (suppressions
de meshes `yahboomcar_description`, 19 fichiers non suivis : `ros2_llm_bridge_cpp/`, `slam3d/`,
`workspace/`…). Elles ne viennent pas de cette session : ne pas les committer en bloc, ne pas les
« nettoyer » sans décision explicite.

---

## 2. Ce qui fonctionne aujourd'hui, mesuré

| Sous-système | État | Preuve |
|---|---|---|
| Base mobile | **proportionnelle** | consigne 0,02 → 0,003 ; 0,05 → 0,052 ; 0,10 → 0,102 (ratio 1,02) |
| Odométrie | **fiable** | dérive latérale 1,57 % sur 1,346 m, cap 0,5° |
| EKF | **actif** | `/odom` 10 Hz + TF `odom→base_link`, stables à l'arrêt (0,0000 m sur 5 s) |
| Lidar TG30 | ok | `/scan` 10,08 Hz, 1296 points |
| Astra Pro+ | ok | couleur 20,06 / profondeur 29,99 / IR 29,97 / points 29,08 Hz |
| Bras + pince | ok | servos relus `[76, 96, 90, 90, 90, 149]` |
| Proprioception | ok | `/arm/servo_angles` 10 Hz, cycle 600 ms, sans casser `/imu` et `/vel_raw` |
| Manipulation | ok | MoveIt planifie et exécute, collision mât modélisée |
| Arbitre réflexe | **actif** | 20 Hz, obstacle 12 cm → zéro en **47 ms**, chien de garde 0,5 s |
| Arrêt du bras par réflexe | **prouvé** | `/safety/hold` → « interrompu par safety hold après 6 échantillons » |
| Directeur | **exécute** | nœud ROS, `/director/command`, un goal par étape, `advance()` sur résultat, annulation sécurité 1,90 ms |
| Sentinel | **actif** | machine IDLE/WATCHING/ENGAGED, YOLO 1 Hz + profondeur, mots d'arrêt locaux, réveil S2 anti-rebondi |
| Audio A2DP | **appairé** | SRS-XB100 `40:72:18:F0:2C:C9`, clé stockée, sink `a2dp_sink`, son testé |
| SLAM | **réparé** | carte 8,1 × 6,5 m, `map→odom` recale 24 cm sur 2,6 m |
| Pont MCP → Hermes | ok | **25 outils**, stdio, `hermes mcp test clawbot` liste les 25 |
| Surface directeur (S2) | ok | `start_skill` / `get_task` / `cancel_task`, tâches terminales consultables, ~2 s par appel |
| Déclenchement S1→S2 | voie CLI | 46,4 s mesuré ; webhook configuré mais passerelle non redémarrée |
| EKF persistant | **en service** | `clawbot-ekf.service`, `/odom` 10,0 Hz, TF `odom→base_link` |
| Nav2 sur carte | **actif** | `clawbot-nav2.service`, 12 nœuds, costmap globale 177×80 (carte du catalogue) |
| Waypoints | **3 nommés** | `ouest` (1,50 ; −0,30), `centre` (2,50 ; 0,00), `est` (5,30 ; 0,48), dégagements 0,65 / 1,05 / 0,75 m |
| `navigate_to` | **exécute** | adaptateur `NavigateToPose`, coordonnées libres refusées, 3 waypoints atteints à 0,000 / 0,121 / 0,082 m en simulation (domaine 99) |
| Préconditions de mouvement | **actives** | bras mesuré sur `/arm/servo_angles` avant tout skill qui déplace la base ; `arm_folded: true` publié sur `/director/state` |
| Contexte MCP | **dérivé** | les absences (`/scan`, `/odom`, cadres TF) sont lues dans l'observation, plus dans une liste figée |
| Caméra du poignet | **dans le graphe** | `/wrist_camera/image_raw` 640×480 `yuv422_yuy2`, cadre `wrist_camera_optical_frame`, 5,98 im/s mesurés (module UVC), latence 8 ms |
| Propriété du périphérique | **unique** | `clawbot-wrist-camera` le tient ; `yolo-inference` lit le topic (`CAMERA_CLAW_SOURCE=ros`) |

**Suite de tests : 293 verts** (pont MCP, seuils, arbitre, contrôleur de bras, EKF, mise à
l'échelle, dérive, round-robin, directeur, surface MCP, exécution des skills, sentinel, catalogue
de waypoints, adaptateur `navigate_to`, cohérence des paramètres Nav2, préconditions de mouvement,
`ExecStop` du directeur, absence dérivée du contexte MCP). Commande exacte :

```bash
cd /home/jetson/clawbot
export ROS_DOMAIN_ID=99
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
source /opt/ros/humble/setup.bash && source install/setup.bash
python3 -m pytest tests/mcp_bridge clawbot_safety/test clawbot_arm_controller/test \
  clawbot_director/test clawbot_sentinel/test tests/test_ekf_config.py \
  tests/test_cmd_vel_scaling.py tests/test_measure_odom_drift.py \
  tests/test_servo_round_robin.py -p no:launch_testing -p no:launch_ros -o addopts="" -q
```

Preuve de bout en bout de la navigation, en simulation, sans déplacer le robot :

```bash
export ROS_DOMAIN_ID=99   # la base virtuelle refuse tout autre domaine
python3 scripts/preuve_navigation_99.py
# 3 waypoints nommes atteints a +/-20 cm, get_task montre les etapes
```

---

## 3. Ce qui a été corrigé pendant cette session (et pourquoi ça compte)

| Défaut | Cause réelle | Correctif | Commit |
|---|---|---|---|
| Base non proportionnelle, signe inversé, pics à 5,6 × | `set_car_type(1)` **ligne 58 du driver** annulait le passage en X3 Plus | suppression, renvoi de `set_car_type(2)` pendant le boot STM32 | `aad2cf0` |
| `/vel_raw` inutilisable par l'EKF | `geometry_msgs/Twist` nu | ajout de `/odom_raw` en `Odometry` avec covariances | `b1525f2` |
| Dérive fantôme de 0,41 m à l'arrêt | accélération linéaire fusionnée (biais intégré) | `imu0_config` : vitesse de lacet seule | `b1525f2` |
| SLAM muet, `map→odom` figée | `base_frame = base_footprint`, frame inexistante | `base_frame:=base_link` | `8d3a901` |
| Arbitre invisible du graphe, `SENSOR_STALE` permanent | service lancé en **root** → découverte DDS isolée | `User=jetson` | `e77dabf` |
| Robot qui continue d'avancer | dernière consigne republiée à 20 Hz | chien de garde 0,5 s | `e77dabf` |
| Garde-fou décoratif | `canceled()` sans demande cliente → transition invalide, **la trajectoire continuait** | `abort()` pour l'arrêt réflexe | `0984414` |
| Directeur sans nœud ROS ni surface | logique pure appelée à la main | `director_node.py`, service `/director/command`, 3 outils MCP, exécution des goals | `9347ff0`…`faa0ce9` |
| Tâche `ACCEPTED` qui restait `RUNNING` pour toujours | aucun skill exécutable | table `skills.py`, refus `INDISPONIBLE` avec le lot manquant, `TIMEOUT` par étape | `faa0ce9` |
| Sentinel absent | — | machine d'attention, mots d'arrêt, réveil anti-rebondi | `50b960a` |
| Aucune sortie audio possible | profils audio désactivés par NVIDIA + module PulseAudio absent | drop-in `zz-audio.conf`, `pulseaudio-module-bluetooth` | `95bd39a` |
| Appairage Bluetooth impossible | noyau qui n'émet jamais `IO_Capability_Request_Reply` | contournement HCI `scripts/appairer_enceinte_bluetooth.sh` | `95bd39a` |

---

## 4. Architecture en place

```text
S2  Hermes ── MCP stdio (25 outils) ──┐        ▲ webhook (réveil, passerelle à redémarrer)
──────────────────────── S1 ──────────┼────────┴──────────────────────────────
  DIRECTEUR                  ARBITRE 20 Hz              SENTINEL (actif)
  /director/command          /cmd_vel → /cmd_vel_safe   attention, mots d'arrêt
  un goal par étape          /safety/hold, /safety/state réveil S2, YOLO 1 Hz
         │                        │
  serveurs d'action        /cmd_vel_safe ── driver ── MCU ── roues
  (bras, pince)            /safety/hold ── contrôleur de bras (abort)
```

**Topics clés** : `/odom_raw`, `/odom`, `/arm/servo_angles`, `/cmd_vel_safe`, `/safety/hold`,
`/safety/state` (`OK|HOLD|FREEZE|DROP_TORQUE|STOP|SENSOR_STALE|BATTERY_LOW`), `/director/state`
(JSON daté), `/sentinel/state`, `/sentinel/event`, `/sentinel/transcript` (couture VAD/STT).

**Services systemd actifs** : `ros2-driver-node`, `clawbot-ekf`, `clawbot-lidar`, `orbbec-camera`,
`clawbot-description`, `clawbot-arm-controller`, `clawbot-move-group`, `clawbot-nav2` (`clawbot-slam`
en conflit déclaré : deux écrivains de `map→odom`), `clawbot-wrist-camera`, `clawbot-safety-arbitrator`,
`clawbot-director`, `clawbot-sentinel`, `clawbot-docs`, `yolo-inference`, `ros2-hardware-service`,
`ros2-llm-bridge-cpp`.

**Paquets créés** : `clawbot_safety`, `clawbot_director` (logique + nœud + skills),
`clawbot_sentinel`, `clawbot_interfaces` (`srv/DirectorCommand`), `clawbot_arm_controller`,
`clawbot_moveit_config`.

---

## 5. Décisions arrêtées (ne pas les rouvrir)

1. Approche **C** : Nav2 garde son BT, nos skills sont des serveurs d'action Python, un directeur
   séquence en JSON, l'arbitre réflexe est un nœud séparé à 20 Hz hors du chemin de planification.
2. S2 envoie des **intentions**, pas des coordonnées.
3. `task_id` obligatoire, registre de tâche unique (`BUSY` sinon).
4. **Préconditions vérifiées par S1**, S2 n'est jamais cru.
5. Priorités **0 sécurité > 0,5 opérateur > 1 voix/Telegram > 2 tâche > 3 opportuniste** ;
   préemption au prochain point sûr.
6. Enceinte Bluetooth en **sortie seule**, STT sur les micros existants (cartes 0 et 1).
7. **Réveil de S2 en fin de tâche**, succès compris, anti-rebond 2 s, repli Telegram si personne.
8. **Échecs hors périmètre** de cette version.
9. Coupure de couple à 12° **seulement si servo 2 < 95°**, sinon maintien figé.
10. « oui » / « non » captés localement **uniquement** en `WAITING_CONFIRMATION`.
11. Proprioception **entrelacée** (1 servo par tick, 1 Hz au repos).
12. Bluetooth : `ControllerMode = bredr` (noyau sans `CONFIG_BT_LE`), et appairage par injection
    HCI documentée — ne pas rejouer la piste « dongle » sans nécessité, l'audio fonctionne.

---

## 6. Ce qui est cassé ou incomplet

| Point | Gravité | Détail |
|---|---|---|
| `DROP_TORQUE` n'actionne rien | **sécurité** | l'état est publié, le contrôleur s'arrête, mais aucun étage ne coupe le couple (`set_uart_servo_torque`). Décision prise, non appliquée. |
| Essai physique des waypoints | bloquant la clôture du lot 5 | la navigation est prouvée en simulation ; aucun déplacement réel n'a encore été commandé par Nav2 |
| Bras absent du costmap de Nav2 | moyen | Nav2 ne connaît le bras que par un rayon d'encombrement de 0,16 m : un waypoint peut être accepté bras en extension |
| Enveloppe du bras non validée | moyen | la précondition refuse un bras hors de la pose de repos mesurée ; cette pose n'a pas été validée par l'opérateur, bras libre (`valide_par_operateur: false`) |
| Skills restants | bloquant lot 6/7 | `arm_move`/`grip_set`/`navigate_to` exécutent ; `follow_human`, `grasp_object`, `search_object`, `express_state`, `look_at_board`, `set_watch_mode` refusent en `INDISPONIBLE` |
| Aucun VAD/STT branché | bloquant lot 7 | `/sentinel/transcript` n'a aucun producteur : les mots d'arrêt sont prouvés en test, inopérants en réel |
| Réveil webhook | moyen | route `clawbot-incident` configurée, passerelle non redémarrée (port 8644 muet) |
| Repli Telegram | moyen | aucun canal configuré ; la règle « personne depuis 60 s → Telegram » n'est pas codée |
| Cause racine Bluetooth | moyen | le noyau ne répond pas à `IO_Capability_Request` ; contournement en place, noyau non instrumentable (`CONFIG_KPROBES`, ftrace functions, `DYNAMIC_DEBUG` absents) |
| Test d'inclinaison réel | moyen | seuils validés sur IMU **simulée** seulement |
| Temps mort base ~0,85 s | moyen | friction statique du MCU, insuffisant pour un asservissement visuel |
| Endpoints de mouvement `:8001` | faible | publient encore sur `/cmd_vel` (3e écrivain, derrière l'arbitre). Les retirer casse le pont C++ historique, encore en service : décision à prendre, pas à subir |
| `joy-teleop` | **corrigé** | unité arrêtée et désactivée le 2026-11-11 : aucun `/dev/input/js*` n'existe sur ce poste |
| Caméra du bras hors graphe | moyen | seule la voie OpenCV la voit |

---

## 7. Pièges appris (à ne pas repayer)

1. **Un service systemd lancé en root est invisible du graphe ROS** : découverte DDS isolée.
   Toujours `User=jetson`, et `Environment=HOME=/home/jetson` (sinon rclpy meurt sur
   `Failed to get logging directory`).
2. **Le driver déployé n'est pas celui du dépôt** : `ros2-driver-node.service` exécute
   `/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/...`. Patcher les deux copies et
   reconstruire **là où le service lit**.
3. **`ros2-driver-node.service` possède `/dev/myserial`** : ne jamais ouvrir le port pendant qu'il
   tourne (sauf script avec verrou, ou driver arrêté).
4. **Les getters du MCU renvoient `-1` sans `create_receive_threading()`** et ~0,4 s d'attente.
5. **`set_car_type` doit être renvoyé pendant le boot du STM32** (reset DTR à l'ouverture du port).
6. **Arrêt serveur = `abort()`, pas `canceled()`** : `canceled()` n'est valide qu'après une demande
   cliente.
7. **`colcon build --symlink-install` casse** certains paquets ament_python de ce dépôt.
8. **pytest + plugin launch_testing** exige `-p no:launch_testing -p no:launch_ros`.
9. **Jamais `ROS_DOMAIN_ID=28` pendant les tests** (ENV-01) : 99 uniquement. `setdefault` ne suffit
   pas : si 28 est déjà exporté, il ne fait rien. La garde doit échouer explicitement.
10. **Le silence d'un flux de sécurité n'est pas un feu vert** : `/safety/state` muet plus de 1 s
    vaut défaut.
11. **Mesurer avec une boucle qui tourne à vide affame l'executor** : la latence DDS passe de 2 ms à
    13 ms si la boucle n'attend pas en dormant. Laisser dormir 0,5 ms par tour.
12. **`ros2 service call` n'est pas un transport JSON** : le CLI réinterprète l'argument en YAML,
    mange les guillemets et casse sur une apostrophe. Passer par `bridge_mcp.director_client`.
13. **Un `ActionServer` rclpy refuse les annulations par défaut** (`default_cancel_callback` →
    REJECT) : sans `cancel_callback` explicite, aucun test d'annulation ne voit rien.
14. **Ne jamais nommer un attribut `_clients` sur un `Node`** : c'est la liste interne rclpy ;
    l'écraser casse l'executor (`'tuple' object has no attribute '_executor_event'`).
15. **Ordre d'arrêt d'un serveur d'action en test** : `executor.shutdown()`, puis `server.destroy()`,
    puis `node.destroy_node()`. L'inverse fait tomber le processus (abort rclcpp).
16. **Bluetooth : le noyau n'émet jamais `IO_Capability_Request_Reply`** sur ce poste (RTL8822CU,
    5.15.148-tegra). L'appairage n'aboutit qu'en injectant la réponse HCI — procédure testée dans
    `scripts/appairer_enceinte_bluetooth.sh`. Le noyau n'a ni `CONFIG_BT_LE`, ni `CONFIG_BT_HS`, ni
    `kprobes`, ni `ftrace` de fonctions : aucune instrumentation possible sans recompilation.
17. **`Pairable` (mgmt `bondable`) n'est pas persistant** : il retombe à `no` à chaque redémarrage
    de `bluetoothd`. Vérifier `bluetoothctl show` juste avant un appairage.
18. **Après un redémarrage de `bluetoothd`, PulseAudio perd la carte `bluez`** et l'enceinte ne se
    reconnecte pas : `scripts/audio_enceinte_defaut.sh` enchaîne connexion, rechargement des modules,
    profil `a2dp-sink` et sink par défaut.
19. **`btmgmt find` est rejeté (`0x0b`) quand `bluetoothd` tourne** : utiliser `bluetoothctl scan on`.
20. **Un nœud Nav2 crée son serveur d'action avant d'être activé** : un goal envoyé à ce moment est
    refusé, et le directeur marque l'étape en échec — à raison. Attendre
    `lifecycle_manager_localization/is_active` **et** `lifecycle_manager_navigation/is_active`,
    pas seulement `wait_for_server()`.
21. **`nav2_costmap_2d` attend `width` et `height` en entiers** : écrire `3.0` fait mourir
    `controller_server` à la construction (`parameter 'height' has invalid type`), sans que le
    reste de la pile signale autre chose qu'un `Waiting for service controller_server/get_state`.
22. **`ekf_node` du paquet Debian de ce poste ne démarre pas** : il linke `libdiagnostic_updater.so`,
    absente en Humble (bibliothèque header-only). Utiliser le binaire du workspace constructeur
    (`yahboomcar_ros2_ws/software/library_ws/install/robot_localization/lib/robot_localization/`)
    avec `LD_LIBRARY_PATH` sur ses bibliothèques, sinon `librl_lib.so` manque.
23. **`/scan` est publié en `laser_link`, pas en `laser`** : le `slam_launch.py` historique déclarait
    `laser`, frame inexistante — les scans étaient muets pour SLAM. Vérifier le `frame_id` réel du
    message avant de déclarer un capteur absent.
24. **`source /opt/ros/humble/setup.bash` tue un script en `set -u`** : les scripts `setup.bash`
    lisent des variables non définies, et un `source` qui échoue sous `set -u` fait sortir le shell
    appelant — le script s'arrête sans message, sans code d'erreur explicite. Un script d'`ExecStop`
    doit donc sourcer sans mode strict et finir par `exit 0`.
25. **Un device V4L2 est exclusif en streaming** : sans erreur côté appelant, le second processus
    meurt sur `Failed mapping device memory`. Un seul propriétaire, les autres lisent le topic —
    `fuser -v /dev/video0` doit montrer un seul processus.
26. **Une unité systemd sans `Environment=ROS_DOMAIN_ID=28` crée son nœud en domaine 0** : le nœud
    apparaît, l'abonnement existe, et aucun message n'arrive, sans la moindre erreur. Le domaine
    est une propriété de l'unité, pas du code.
27. **`rclpy` s'importe depuis le venv `yolov5_env` à condition de sourcer `/opt/ros/humble`** : les
    deux Python sont 3.10. C'est ce qui permet à un service GPU de consommer un topic ROS sans
    second bridge.
28. **Le bord de la carte n'est pas de l'espace libre** : un champ de distance calculé sur les
    seules cellules occupées désigne les coins non observés comme les points les plus sûrs. Le bord
    doit compter comme obstacle, sinon un waypoint proposé automatiquement tombe hors de la pièce.

---

## 8. Prochaines étapes, dans l'ordre

### Brique 1 — nœud ROS du directeur — **faite**
Nœud `director`, `/director/command`, `/director/state` daté ; porte d'entrée « OK frais », chien de
garde 1,0 s, une seule annulation journalisée par défaut. Annulation sécurité mesurée **médiane
1,90 ms, p95 2,2 ms, max 2,9 ms** sur 20 essais (domaine 99). Ce chiffre mesure le passage de la
tâche à `CANCELLED_SAFETY`, pas l'arrêt physique (`/safety/hold` pour le bras, `goal_cancel` pour
les actions).

### Brique 2 — surface MCP — **faite**
Service `/director/command` (`clawbot_interfaces/srv/DirectorCommand`, JSON en entrée et en
sortie), quatre opérations (`start_skill`, `start_sequence`, `get_task`, `cancel_task`, plus
`confirm` ajouté pour le sentinel), trois outils MCP, catalogue à **25 outils**. Énumération fermée
des skills, motif `safety` interdit à S2, `UNKNOWN_TASK` → `MCP-E-ARG`. Coût **~2,0 s** par appel
(client rclpy ponctuel).

### Brique 3 — exécution réelle — **faite**
`skills.py` traduit une étape en goal ; `advance()` sur le résultat ; `TIMEOUT` par étape ; goal
annulé sur sécurité, `cancel_task` et délai ; `BUSY` avant validation du skill. Primitives
`arm_move`/`grip_set` ; skills de la spec refusés en `INDISPONIBLE` avec leur lot. **Aucun mouvement
réel** : `arm_move` n'a jamais été lancé sur le robot.

### Brique 4 — sentinel — **faite**
Machine `IDLE → WATCHING → ENGAGED` (2 frames, 0,75 / 3,5 m, absence 10 s, cooldowns 60 s / 5 s),
mots d'arrêt locaux (« stop », « arrête-toi », « halte ») qui coupent la tâche et mettent
`/cmd_vel` à zéro, « oui »/« non » seulement en `WAITING_CONFIRMATION`, réveil `TASK_TERMINAL`
anti-rebondi 2 s + mémoire du `task_id`, échec de POST journalisé avec `delivered: false`.
23 tests, trois mutations vérifient leur pouvoir de discrimination.

### Brique 5 — cartographie, waypoints et Nav2 — **faite en simulation, essai physique à faire**
- catalogue **en énumération fermée** : `config/waypoints.yaml`, trois waypoints (`ouest`
  1,50/−0,30, `centre` 2,50/0,00, `est` 5,30/0,48) mesurés sur la carte
  `test_cartographie_apres_deplacement`, dégagements 0,65 / 1,05 / 0,75 m, même composante connexe ;
- résolution nom → pose dans `clawbot_director/waypoints.py` : refus des coordonnées libres, huit
  catalogues malformés refusés au chargement (doublon, non fini, hors bornes, clé inconnue, nom
  invalide) ;
- `navigate_to` n'est plus `INDISPONIBLE` : `skills.py` construit un goal `NavigateToPose` en
  `map`, horodatage nul (TF la plus récente), délai 90 s ;
- Nav2 déployé par `clawbot-nav2.service` (`config/nav2_clawbot.yaml`, `launch/navigation.launch.py`
  qui **déduit la carte du catalogue**), AMCL + NavFn + Regulated Pure Pursuit ;
- EKF enfin persistant (`clawbot-ekf.service`) : sans `/odom` ni TF, rien de tout cela ne tenait ;
- **preuve** : `scripts/preuve_navigation_99.py` (base virtuelle + scan par lancer de rayons sur la
  vraie carte + Nav2 avec les paramètres du robot) → 3 waypoints atteints à **0,000 / 0,121 /
  0,082 m**, `get_task` à 3/3, `DONE` ;
- **reste** : l'essai physique des trois waypoints, robot au sol, opérateur présent. C'est le seul
  critère de sortie du lot qui ne soit pas encore mesuré sur le matériel. Protocole dans
  `docs/knowledge-base/02_Software/navigation_nav2_waypoints.md` §6, et
  `scripts/poser_pose_initiale.py` pour déclarer la pose réelle à AMCL.

### Brique 6 — perception et saisie — **première moitié faite**
Caméra du poignet **dans ROS** depuis le 2026-11-11 16:50 CET :
- `clawbot-wrist-camera.service` : `v4l2_camera_node` sur le chemin by-id, 640×480, encodage natif
  `yuv422_yuy2`, cadre `wrist_camera_optical_frame` ;
- cadre optique dans l'URDF, **enfant de `mono_link` sur `arm_link4`** (le montage physique existait
  déjà ; `arm_link5` aurait décrit un second montage) ;
- **un seul propriétaire du périphérique** : `yolo-inference.service` lit désormais
  `/wrist_camera/image_raw` (`CAMERA_CLAW_SOURCE=ros`) au lieu d'ouvrir l'index V4L2 — deux
  processus sur un device V4L2 se volaient les tampons ;
- calibration `config/wrist_camera_info.yaml` **déclarée non mesurée** (`fx=fy=457 px`, demi-champ
  35°, aucune mire) ;
- **mesure** : 5,98 im/s au niveau du périphérique (limite du module, insensible à la résolution,
  au lien et à la charge), latence 8 ms ; critère du lot corrigé de 15 Hz à « au moins 5 im/s ».

**Reste de la brique** : cadrage et netteté à vérifier bras en mouvement (l'image actuelle est
sans détail, netteté 7,3), orientation du cadre optique à confirmer en visant une cible, puis
`search_object`, `grasp_object` (boucle fermée à 6 Hz, tolérance à mesurer) et `follow_human`.
Page : `docs/knowledge-base/02_Software/camera_poignet.md`.

### Brique 7 — parole et audio
VAD Silero + faster-whisper tiny sur les micros existants → publication sur
`/sentinel/transcript` (la couture existe déjà), Piper TTS sur la sortie A2DP désormais validée,
`express_state` sur LED/buzzer.

### Dettes à traiter en parallèle
- `DROP_TORQUE` (coupe de couple servo) — opérateur présent.
- `ExecStop` du directeur qui annule et publie.
- test d'inclinaison réel.
- arrêter `joy-teleop`, déprécier les endpoints de mouvement de `:8001`.
- redémarrer la passerelle Hermes pour activer le webhook (coupe la session en cours : `--yes`),
  ou coder le repli Telegram.

---

## 9. Commandes utiles

```bash
# état des services
systemctl is-active ros2-driver-node clawbot-safety-arbitrator clawbot-arm-controller \
  clawbot-director clawbot-sentinel clawbot-slam clawbot-docs

# chaîne de sécurité, bras et sentinel
ros2 topic echo /safety/state --once
python3 scripts/etat_directeur.py        # état, sécurité, angles de bras, arm_folded
ros2 topic echo /sentinel/state --once
ros2 topic hz /arm/servo_angles

# navigation (domaine 99 pour toute preuve, jamais 28)
systemctl is-active clawbot-ekf clawbot-nav2 clawbot-slam
ros2 run tf2_ros tf2_echo map base_link
python3 scripts/poser_pose_initiale.py ouest          # domaine 28, robot posé sur le waypoint
echo '{"op":"start_skill","skill":"navigate_to","args":{"destination":"centre"}}' \
  | python3 -m bridge_mcp.director_client
ROS_DOMAIN_ID=99 python3 scripts/preuve_navigation_99.py

# base
ROS_DOMAIN_ID=28 python3 scripts/base_probe_l1.py --speed 0.05 --duration 3

# preuve réflexe -> bras (domaine 99, sûr)
ROS_DOMAIN_ID=99 python3 scripts/test_safety_hold.py

# directeur (après source /opt/ros/humble/setup.bash et install/setup.bash) : JSON sur stdin
echo '{"op":"get_task"}' | python3 -m bridge_mcp.director_client
echo '{"op":"start_skill","skill":"arm_move","args":{"positions":[0,0,0,0,0],"duration_s":1}}' \
  | python3 -m bridge_mcp.director_client
echo '{"op":"cancel_task","reason":"operateur"}' | python3 -m bridge_mcp.director_client

# audio Bluetooth
./scripts/audio_enceinte_defaut.sh          # reconnexion + sink par défaut
paplay /usr/share/sounds/alsa/Front_Center.wav
# appairage (enceinte en mode appairage, après désappairage ou reset seulement)
sudo ./scripts/appairer_enceinte_bluetooth.sh 40:72:18:F0:2C:C9

# documentation
sudo systemctl restart clawbot-docs && curl -s -o /dev/null -w '%{http_code}\n' \
  http://127.0.0.1:8080/knowledge-base/02_Software/directeur_s1/
```

---

## 10. Documentation

- Base OKF : `/Robot_Knowledge_Base` (**55 fichiers, 0 erreur**), publiée sur `:8080`.
- Conception : `docs/superpowers/specs/2026-11-11-architecture-s1-s2-design.md`
- Plan : `docs/superpowers/plans/2026-11-11-architecture-s1-s2.md`
- Pages clés : `inventaire_materiel`, `slam_cartographie`, `systeme1_arbitre`, `directeur_s1`,
  `sentinel_s1`, `srs_xb100`, `mcp_hermes`, `manipulation_moveit`,
  `ERR-2026-11-11-010_base_non_proportionnelle`, `ERR-2026-11-11-011_bluetooth_appairage_sans_ble`,
  `2026-11-11_compte_rendu_bluetooth_srs_xb100`.
- Scripts de la session : `scripts/appairer_enceinte_bluetooth.sh`,
  `scripts/audio_enceinte_defaut.sh`, `clawbot_director/test/soutien_actions.py` (faux bras).

## 11. Derniers commits

```text
0ea832f feat(perception): camera du poignet dans ROS, proprietaire unique du peripherique
2d36f24 feat(director): preconditions de mouvement, ExecStop, absences derivees
a0bbea3 feat(nav2): navigation sur carte, catalogue de waypoints ferme, navigate_to
95bd39a feat(audio): enceinte SRS-XB100 appairee, A2DP verifie, procedure conservee
0807648 docs(okf): directives BR/EDR + cache + MGMT appliquees, meme blocage HCI
d18f000 docs(okf): compte rendu de reprise sur l'appairage Bluetooth SRS-XB100
c5fa0bd docs(okf): ERR-011 appairage Bluetooth impossible, noyau sans BLE
50b960a feat(sentinel): attention IDLE/WATCHING/ENGAGED, mots d'arret locaux, reveil S2
d032e5c docs(okf): page directeur S1 (machine d'etats, garde-fous, skills, surface MCP)
faa0ce9 feat(director): execution des skills, advance() sur le resultat des goals
9c92424 feat(director): surface MCP start_skill/get_task/cancel_task
```
