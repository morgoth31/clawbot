# État du projet Clawbot — reprise de session

**Date** : 2026-11-11 19:30, reprise en cours (lot 5 clos, brique 6 à moitié, **bras remis en
service et pose de repos validée**)
**Branche** : `docs/site-okf-merge` ; dernier commit `c6ac7c1`
**Prochaine action, dans l'ordre** : (1) ~~le test d'une minute qui départage la panne du bras~~ —
fait, le bras bouge, §8 « bras » ; (2) l'essai physique des waypoints, robot au sol ; (3) la
cohérence des caméras du sentinel — §8 « dettes ».
**Robot** : Clawbot X3 Plus, Jetson Orin NX, ROS 2 Humble, domaine 28

> Ce document est fait pour être lu **au début d'une nouvelle session**, à la place d'un
> historique de conversation. Il dit ce qui marche, ce qui est mesuré, ce qui casse, ce qui
> reste, et dans quel ordre continuer.

---

## 1. Comment reprendre

Ouvrir une nouvelle session et envoyer :

> Lis `/home/jetson/clawbot/docs/ETAT-PROJET.md` et
> `docs/superpowers/specs/2026-11-11-architecture-s1-s2-design.md`, puis commence par le §8
> « bras » : c'est le seul point bloquant, et il se tranche en une minute.

Les briques 1 à 5 sont faites : nœud ROS du directeur, surface MCP, exécution réelle des goals,
sentinel, navigation sur carte avec waypoints fermés. La brique 6 est à moitié faite : la caméra du
poignet est dans ROS. Ne pas refaire ces briques. Ne pas relancer les diagnostics déjà faits : ils
sont tous dans ce document avec leurs chiffres et leur date.

**Deux choses ne sont pas closes** : l'essai **physique** des trois waypoints (robot au sol), et la
cohérence des caméras du sentinel (§8, dettes). La panne du bras est levée (§8) : les servos
exécutent, la pose de repos validée par l'opérateur est `[90, 180, 0, 0, 90, 149]` et elle est
inscrite dans `config/preconditions.yaml`.

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
| Bras + pince | **exécute** | 2026-11-11 19:05-19:20 : servo 2 (10°), servo 4 (90°), servo 3 (90°), servo 1 (14°) exécutés, prouvés par l'image frontale (barycentre du masque de la pince 353 → 301 px, étendue au repos ±0,9 px) |
| Proprioception | ok | `/arm/servo_angles` 10 Hz, cycle 600 ms, sans casser `/imu` et `/vel_raw` ; **relecture = mesure** depuis 19:12 (valeur intermédiaire 35° jamais commandée) |
| Pose de repos / déplacement | **validée par l'opérateur** | `[90, 180, 0, 0, 90, 149]` — bras debout, caméra du poignet vers l'avant ; `arm_folded: true` publié sur `/director/state` |
| Manipulation | **débloquée** | MoveIt2 était mort : `base_link` avait deux parents TF, `pick_ik` répondait `COLLISION_CHECKING_UNAVAILABLE` même sur la pose courante. Corrigé le 2026-11-11 19:55 (`odom → base_footprint`), `/compute_ik` répond `SUCCESS` ; collision mât modélisée (`camera_support`) |
| Portée du bras | **mesurée, limitante en distance** | `/compute_fk` sur tout l'espace articulaire : les doigts descendent à z = −0,115 m dans `base_link`, soit **5 cm sous le niveau du sol** (−0,064 m) ; portée horizontale **0,439 m**. La contrainte est la distance, pas la hauteur : un objet au sol est saisissable si le robot avance à moins de ~0,40 m |
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
| Préconditions de mouvement | **actives, enveloppe validée** | bras mesuré sur `/arm/servo_angles` avant tout skill qui déplace la base ; enveloppe ±5° autour de la pose validée ; `arm_folded: true` publié sur `/director/state` |
| Contexte MCP | **dérivé** | les absences (`/scan`, `/odom`, cadres TF) sont lues dans l'observation, plus dans une liste figée |
| Caméra du poignet | **dans le graphe** | `/wrist_camera/image_raw` 640×480 `yuv422_yuy2`, cadre `wrist_camera_optical_frame`, 5,98 im/s mesurés (module UVC), latence 8 ms |
| Propriété du périphérique | **unique** | `clawbot-wrist-camera` le tient ; `yolo-inference` lit le topic (`CAMERA_CLAW_SOURCE=ros`) |

**Suite de tests : 303 verts** (pont MCP, seuils, arbitre, contrôleur de bras, EKF, mise à
l'échelle, dérive, round-robin, directeur, surface MCP, exécution des skills, sentinel, catalogue
de waypoints, adaptateur `navigate_to`, cohérence des paramètres Nav2, préconditions de mouvement,
`ExecStop` du directeur, absence dérivée du contexte MCP, caméra du poignet). Commande exacte :

```bash
cd /home/jetson/clawbot
export ROS_DOMAIN_ID=99
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
source /opt/ros/humble/setup.bash && source install/setup.bash
python3 -m pytest tests/mcp_bridge clawbot_safety/test clawbot_arm_controller/test \
  clawbot_director/test clawbot_sentinel/test tests/test_ekf_config.py \
  tests/test_cmd_vel_scaling.py tests/test_measure_odom_drift.py \
  tests/test_servo_round_robin.py tests/test_camera_poignet.py \
  -p no:launch_testing -p no:launch_ros -o addopts="" -q
# 303 passed
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
| Cause de la panne du 17:20 | moyen | le symptôme a disparu après redémarrage du pilote (17:36:06) et du contrôleur (17:37:13) ; aucun test entre 17:37 et 19:04, aucune cause racine établie. À instrumenter si elle revient |
| Bras absent du costmap de Nav2 | moyen | Nav2 ne connaît le bras que par un rayon d'encombrement de 0,16 m : un waypoint peut être accepté bras en extension |
| Encombrement de la pose de repos | moyen | la pose `[90, 180, 0, 0, 90, 149]` est **validée par l'opérateur** (`valide_par_operateur: true`), mais son volume balayé n'est pas mesuré au mètre ; seule la géométrie du mât sert de référence |
| Cadre optique du poignet | **corrigé le 2026-11-11 20:20** | `rpy` du joint optique passé de `(-1.5708 0 -1.5708)` à `(0 0 -1.5708)` : axe horizontal à la pose de repos (vérifié), −40° à `servo 2 = 140`. Intrinsèques portées de `fx=457` à **2300 px**. Test de régression dans `tests/test_camera_poignet.py` |
| Bus servo muet | **bloquant le bras** | depuis ~20:35, les six servos ne répondent **ni en lecture ni en mouvement** : lecture directe pilote arrêté = −1 ×6, consigne `set_uart_servo_angle(1, 85)` sans effet (0,7 px d'écart image = le bruit). Le MCU est sain (version 3.5, 11,90 V, IMU). Cycle d'alimentation à faire ; protocole et verdict dans [[2026-11-11_essai_prehen_stylo]] §9.1 |
| Skills restants | bloquant lot 6/7 | `arm_move`/`grip_set`/`navigate_to` exécutent ; `follow_human`, `grasp_object`, `search_object`, `express_state`, `look_at_board`, `set_watch_mode` refusent en `INDISPONIBLE` |
| `grasp_object` et la portée | **contrainte de distance** | les doigts descendent 5 cm sous le niveau du sol, donc un objet au sol **est** saisissable ; mais la portée n'est que de 0,439 m : le robot doit avancer à moins de ~0,40 m de l'objet, et le stylo mesuré le 2026-11-11 20:20 était à 0,50 m |
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
28. **`/arm/servo_angles` n'est pas une preuve de position.** Le 2026-11-11 17:35, pilote arrêté,
    `get_uart_servo_angle_array()` a rendu exactement les consignes envoyées alors que le bras
    n'avait pas bougé : le MCU renvoie son registre de consigne. Le 2026-11-10 le même canal
    retardait sur la consigne quand un servo forçait — la lecture était alors une mesure. Ne jamais
    conclure « le bras a bougé » sur une valeur qui suit la consigne : seule une valeur qui en
    **diffère** prouve que le servo travaille. Depuis le 2026-11-11 19:12 la lecture est de nouveau
    une mesure (35° relevés pour une consigne 20° → 40°), mais un pas de 10° est trop court pour que
    la relecture entrelacée (un servo par 600 ms) en attrape une valeur intermédiaire : l'absence de
    valeur intermédiaire sur un petit pas ne prouve pas un blocage.
29. **Un `systemctl stop ros2-driver-node` met la pile en cascade** (`Requires=`) : arbitre,
    contrôleur de bras, directeur, sentinel et Nav2 tombent en `failed`, et relancer le seul pilote
    ne les relance pas. Toujours `systemctl list-units --state=failed` puis relance dans l'ordre
    `driver → ekf → arbitre → description → bras → directeur → caméra → nav2 → sentinel → yolo`.
    Une session entière a été menée avec six unités mortes sans que rien ne le signale.
30. **Le bord de la carte n'est pas de l'espace libre** : un champ de distance calculé sur les
    seules cellules occupées désigne les coins non observés comme les points les plus sûrs. Le bord
    doit compter comme obstacle, sinon un waypoint proposé automatiquement tombe hors de la pièce.
31. **Un lien ne peut avoir qu'un seul parent dans TF.** `base_link` en avait deux — la description
    (`base_footprint → base_link`, URDF) et l'EKF (`odom → base_link`) — et TF gardait **deux arbres
    déconnectés** : `base_footprint`, racine du modèle et cadre de planification par défaut de
    `move_group`, restait orphelin. Symptômes trompeurs : `pick_ik` répond
    `COLLISION_CHECKING_UNAVAILABLE` (-21) **même sur la pose courante**, toute planification échoue
    en `FAILURE` sans autre motif, et des avertissements « not part of the same tree » défilent pour
    chaque cadre. Correctif : l'EKF publie `odom → base_footprint`. Vérification :
    `tf.all_frames_as_yaml()` doit montrer **une seule racine** et un seul parent par lien.
32. **La hauteur du sol se mesure par histogramme, pas par percentile sur une bande d'image.** Un
    percentile des z dans le bas de l'image a donné −0,414 m alors que le sol est à −0,064 m : la
    bande contenait le châssis et le plan incliné de la caméra, et toute la conclusion en a été
    inversée. Prendre le **pic de l'histogramme des z** sur toute l'image et vérifier qu'il couvre une
    grande étendue en x, puis recalculer la portée avec cette valeur.
33. **La caméra du poignet est à 90° de l'axe de la pince.** Une configuration qui pose les doigts sur
    un objet peut donc tourner l'objectif vers le plafond : à `q = [0, −1,00, −0,80, +1,57, 0]` le
    modèle annonce **+67°** et l'image ne montre qu'un plafonnier. Pour un asservissement visuel final,
    chercher les poses qui satisfont **les deux** — pince sur le point et point sur l'axe optique —
    avec `scripts/pose_saisie_vue.py` ; sur le point du stylo il en existe 396, la meilleure à
    `j2 = 0, j3 = −1,50, j4 = −0,20`.
34. **Un `-1` sur `/arm/servo_angles` n'est pas un servo mort — mais ce n'est pas rien non plus.** C'est
    la valeur de retour des getters du MCU quand la transaction échoue. Le protocole qui tranche, en
    4 minutes : pilote arrêté, lecture directe par `Rosmaster_Lib`, puis **test d'écriture mesuré sur
    l'image** (une consigne de 5° doit déplacer le barycentre de la pince de dizaines de pixels). Le
    2026-11-11, lecture et écriture étaient muettes alors que version, tension et IMU répondaient :
    le MCU était sain, le bus servo mort.

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

### Panne du bras — **tranchée le 2026-11-11 19:20**
Le test d'une minute a répondu : **le bras bouge**. Paliers exécutés dans la séance, tous relus à
la cible et sans défaut de sécurité (`/safety/state = OK`) : servo 2 de 97° à 87° et retour, servo 4
de 90° à 0°, servo 3 de 90° à 0°, servo 1 de 76° à 90°, servo 2 de 97° à 180°.

Preuves, parce que la relecture ne suffisait pas :

- **image frontale** : barycentre du masque sombre de la pince, stable à ±0,9 px au repos, déplacé de
  353 → 301 px pour les 10° du servo 2 (carte des différences localisée sur la silhouette, fond
  inchangé) ;
- **relecture** : une consigne 20° → 40° sur le servo 4 a fait passer la lecture par **35°**, valeur
  jamais commandée — c'est une mesure, plus un registre.

**Ce qui n'est pas établi** : la cause de la panne de 17:20. Le seul changement d'état visible entre
les observations de 17:20-17:35 et la reprise de 19:05 est le redémarrage du pilote (17:36:06) et du
contrôleur de bras (17:37:13) ; aucun test du bras n'a eu lieu entre 17:37 et 19:04. Un redémarrage
qui efface le symptôme ne dit pas ce qui l'a produit : si elle revient, instrumenter le journal du
pilote avant tout redémarrage.

Trois faits sortis de ce test, à garder :

1. **la pose de repos change** : `[90, 180, 0, 0, 90, 149]`, validée par l'opérateur comme position
   de déplacement — bras debout, caméra du poignet tournée vers l'avant dans le même sens que
   l'Astra. Elle est dans `config/preconditions.yaml` (`valide_par_operateur: true`, ±5°), et
   `arm_folded` vaut `true` sur le robot dans cette pose ;
2. **le seuil de collision du mât dépend de q3 et q4** : la montée du servo 2 de 97° à 180° s'est
   faite sans contact, segments à x ≈ 0,015 m contre un mât à x ≈ −0,044 m, alors que la base
   documentait un contact à ≈ 114° dans une autre configuration ;
3. **la caméra du poignet était blanche, ce n'était pas la netteté** : `gain=70`/`brightness=60`
   saturaient les 307 200 pixels à 255 ; à `gain=0` l'image redevient exploitable (min 8, max 224,
   écart-type 61). Les réglages de l'unité restent à corriger.

Page complète, chaîne, faits datés et protocole : `docs/knowledge-base/02_Software/bras_remise_en_service.md`.

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

**Fait depuis, le 2026-11-11 à 19:45** (le bras fonctionne, donc les deux mesures bloquées sont
faites) : cadrage et netteté mesurés **pose par pose** avec `scripts/mesure_cadrage_poignet.py` —
netteté 55 sur un parquet uni, 85 sur un couloir, **225 à 253 sur un visage à 40-70 cm**, 0 % de
pixels saturés à `gain=0`. Le « netteté 7,3 » d'origine venait d'une image plate et saturée, pas de
la mise au point. L'écart d'orientation du cadre optique est chiffré : **+90° en tangage** (le modèle
annonce −90° là où l'image montre l'horizon, et −130° à `servo 2 = 140` où l'image montre le sol).
La pose utile à la saisie est `servo 2 ≈ 120-150` ; à la pose de repos la caméra regarde l'horizon.

**Reste de la brique** : `search_object`, `grasp_object` (boucle fermée à 6 Hz, tolérance à mesurer)
et `follow_human`. Le repère du poignet n'étant pas corrigé dans l'URDF, `grasp_object` doit viser
sur l'image, pas sur `z_optique`.
Page : `docs/knowledge-base/02_Software/camera_poignet.md`.

### Brique 7 — parole et audio
VAD Silero + faster-whisper tiny sur les micros existants → publication sur
`/sentinel/transcript` (la couture existe déjà), Piper TTS sur la sortie A2DP désormais validée,
`express_state` sur LED/buzzer.

### Dettes à traiter en parallèle
- **cohérence des caméras du sentinel** : `clawbot_sentinel` interroge `/detect_raw` **sans**
  préciser de caméra, donc le service YOLO répond avec `claw` — la caméra du poignet — alors que la
  distance vient de la profondeur de l'Astra. Détections et distances viennent de deux points de vue
  différents. Le mode source ROS existe désormais : passer `CAMERA_FRONT_SOURCE=ros` +
  `CAMERA_FRONT_ROS_TOPIC=/camera/color/image_raw` et faire pointer le sentinel sur
  `?camera=front`. C'est la correction que l'opérateur a demandée le 2026-11-11.
- **REQ-HEALTH-005 non tenue — moniteur de santé trop coûteux (P05, 2026-11-22)** : le moniteur
  consomme **14,32–15,68 % d'un cœur** pour un budget de 5 %. Hors flux image il tombe à **2,56 %**
  (version C++, donc sous le budget) ; les trois flux image (`/camera/color/image_raw`,
  `/camera/depth/image_raw`, `/wrist_camera/image_raw`, ≈ 52 messages/s de 0,6 à 1,2 Mo) coûtent
  ~12 points par recopie de la charge utile, et cette pile n'offre aucune zéro-copie exploitable.
  Mesures, cause et pistes : `deploy/journal/2026-11-22_p05_rapport.md` §5.
  **À trancher par l'opérateur** : budget révisé, prêts DDS zéro-copie (éditeurs compatibles
  requis), ou surveillance des images portée par le nœud de perception en P12.
- `DROP_TORQUE` (coupe de couple servo) — opérateur présent ; `set_uart_servo_torque` existe.
- **`joy_teleop/clawbot_restart_teleop.sh` hors INV-08 (P07, 2026-11-22)** : l'outil manuel de
  redémarrage de la téléopération contient encore **trois `pkill -f`** (`clawbot_joy_teleop.py`,
  `joy_teleop_launch.py`) et deux `pkill -x`. Le fichier est **modifié hors de la zone de travail**
  de P07 et n'a pas été touché ; l'étape `interdits` de `scripts/check.sh` le cite donc en exception
  nommée. **À reprendre avec le fichier d'origine** : remplacer ces motifs par un arrêt des unités
  systemd concernées (`clawbot-joy-teleop.service`), puis retirer l'exclusion de `check.sh`.
  **À trancher par l'opérateur** (propriétaire de ce fichier).
- **Réarmement de l'e-stop : le relâchement de l'entrée n'est spécifié nulle part (P10, 2026-11-22)** :
  `/safety/reset_estop` (et `POST /estop/reset` sur 8001) refusent de lever le verrou tant que
  `/safety/estop` vaut `true`, mais **aucun composant ne publie `false`** : la sentinelle ne publie
  que `true` au mot d'arrêt (`sentinel_node.py:165`), il n'existe ni mot de reprise, ni service de
  relâchement. Le seul chemin constaté est une publication `false` manuelle sur `/safety/estop`
  (faite une fois, sous délégation, pour débloquer P10). **Recommandation** : porter le geste sur la
  sentinelle, derrière un service explicite `release_estop` (`std_srvs/Trigger`) exposé seulement à
  la route authentifiée du tableau de bord, qui publie `false` **une fois**, journalise l'auteur et
  l'heure, et refuse si une autre source maintient encore `true`. À écarter : un mot de reprise
  vocal (un mot mal entendu ne doit jamais lever un verrou de sûreté) ; à préférer si un bouton
  physique arrive : relayer son état relâché plutôt que d'ajouter un service.
  **À trancher en P13 (le bras doit bouger) ou P14.**
- test d'inclinaison réel.
- déprécier les endpoints de mouvement de `:8001` (casse le pont C++ historique : décision à
  prendre, pas à subir). `joy-teleop` est arrêté et désactivé depuis le 2026-11-11.
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

# bras : un pas, avec relecture qui attend le cycle de proprioception (install/ obligatoire)
source /home/jetson/clawbot/install/setup.bash
python3 scripts/pas_bras.py --servo 2 --vers 170 --max-pas 10
python3 scripts/cinematique_bras.py --q 90,180,0,0,90     # pose de repos validee
python3 scripts/test_couple_bras.py --servo 4 --pas 5      # couple + un pas, pilote arrete
python3 scripts/read_arm_angles.py                          # lecture directe du bus

# camera du poignet
systemctl is-active clawbot-wrist-camera && ros2 topic hz /wrist_camera/image_raw
python3 scripts/capture_compressee.py --topic /wrist_camera/image_raw/compressed --out /tmp/p.png

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

- Base OKF : `/Robot_Knowledge_Base` (**59 fichiers, 0 erreur**), publiée sur `:8080`.
- Conception : `docs/superpowers/specs/2026-11-11-architecture-s1-s2-design.md`
- Plan : `docs/superpowers/plans/2026-11-11-architecture-s1-s2.md`
- Pages clés de cette session : `navigation_nav2_waypoints`, `preconditions_mouvement`,
  `camera_poignet`, `bras_remise_en_service`.
- Pages clés : `inventaire_materiel`, `slam_cartographie`, `systeme1_arbitre`, `directeur_s1`,
  `sentinel_s1`, `srs_xb100`, `mcp_hermes`, `manipulation_moveit`,
  `ERR-2026-11-11-010_base_non_proportionnelle`, `ERR-2026-11-11-011_bluetooth_appairage_sans_ble`,
  `2026-11-11_compte_rendu_bluetooth_srs_xb100`.
- Scripts de la session : `scripts/appairer_enceinte_bluetooth.sh`,
  `scripts/audio_enceinte_defaut.sh`, `clawbot_director/test/soutien_actions.py` (faux bras).

## 11. Derniers commits

```text
c6ac7c1 docs(bra): chaine de commande du bras, faits dates, pieges et test qui departage
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
