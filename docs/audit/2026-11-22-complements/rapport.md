# Mesures complémentaires du 2026-11-22 — P01

Mesures en lecture seule, domaine DDS 28 uniquement pour lire (`ros2 topic
list/info/hz/echo --once`, `ros2 node info`), jamais pour publier. Chaque sortie
brute est dans `raw/Mxx_<nom>.txt`, précédée de sa date ISO et de la commande.

**Trois réponses en tête**

1. **Mémoire partagée Fast DDS : ACTIVE.** 85 segments `fastrtps_*` dans
   `/dev/shm`, 11 Mo réellement occupés (M01).
2. **Délai d'arrêt du pilote sur silence : ABSENT.** Aucun watchdog dans le
   pilote ni dans `Rosmaster_Lib` ; la dernière consigne reste appliquée par le
   MCU (M04).
3. **Propriétaires du port série : 1 par périphérique.** `Mcnamu_driver_X3`
   (PID 3115) sur `ttyUSB0`, `ydlidar_ros2_driver_node` (PID 3614) sur
   `ttyUSB1` ; `hardware_service.py` n'ouvre aucun port série (M05).

## Tableau récapitulatif

| ID | Question | Résultat | Conclusion |
|---|---|---|---|
| M01 | SHM Fast DDS utilisée ? | 85 segments `fastrtps_*`, 11 Mo / 7,7 Go, aucune unité ne pose `FASTRTPS_DEFAULT_PROFILES_FILE`, `RMW_IMPLEMENTATION` ni `ROS_LOCALHOST_ONLY` | SHM active par défaut (Fast DDS 2.6) |
| M02 | Radio Wi-Fi porte-t-elle l'image ? | Wi-Fi TX 4 065 o/s (32,5 kbit/s), RX 2 032 o/s ; boucle locale 37,4 Mo/s ; image 640×480 yuv422 30 Hz = 18,4 Mo/s | Image sur boucle locale, pas sur la radio |
| M03 | Domaine 28 visible du réseau ? | NON MESURÉ — exige un second poste | — |
| M04 | Arrêt moteurs sans consigne ? | Aucun watchdog ; `set_car_motion` écrit une trame unique | Délai d'arrêt absent |
| M05 | Qui ouvre le port série ? | 1 processus par device ; `by-id` du MCU = `usb-1a86_USB_Serial-if00-port0` | `hardware_service` n'y touche pas |
| M06 | Topologie USB | Astra sur bus 1 à **480 Mb/s** derrière hubs VIA ; bus 3 (5 000 Mb/s) vide | Astra en USB 2.0 |
| M07 | Charge CPU instantanée | Somme 142 % (8 cœurs) ; cœur le moins chargé cpu4 à 22,1 % | `ps` surestime (moyennes sur 7 j) |
| M08 | Ports en écoute | 8000 `api_server`, 8001 `hardware_service`, 8003 `yolo_service`, 9090 rosbridge, 8080 mkdocs, 8888/8889/8081/8644/22/111/631/3389 | tout en 0.0.0.0 sauf 11434/11539/60589/53 |
| M09 | Intentions des 3 éditeurs de `/cmd_vel` | `hardware_service` (à la demande + watchdog 1,5 s), pont C++ (secours Stop), sentinelle (arrêt local) | aucun éditeur périodique de consigne non nulle |
| M10 | Outils MCP | 25 outils, serveur `bridge_mcp.stdio` lancé sur ce Jetson | Hermes tourne sur le Jetson |
| M11 | Bras, MoveIt, Nav2 arrêtés ? | 3 unités activées, jamais démarrées, aucune erreur | arrêt volontaire, pas une panne |
| M12 | Lancement de l'Astra | par `orbbec-camera.service`, pas par `hardware_service` ; 640×480@30 profondeur et couleur | erreurs USB : 2 `tegra-xusb` seulement |
| M13 | Éditeurs de `/joint_states` | 2 déclarés, 1 seul publie (JSP, 20 Hz, 15 joints à 0,0) ; éditeur du pilote mort | positions articulaires jamais publiées |

## M01 — Mémoire partagée Fast DDS

- Commandes : `ls -la /dev/shm`, `ls /dev/shm | grep -c fastrtps`, `df -h /dev/shm`,
  `systemctl show <unité> -p Environment` pour 8 unités.
- Résultat (2026-11-22T12:38:23+01:00) : 85 fichiers `fastrtps_*`, 549 408 o de
  taille apparente chacun, `df` = 11 Mo occupés sur 7,7 Go. Les dates vont du
  15 au 22 novembre : mélange de segments de participants vivants et de résidus
  non supprimés. Aucune unité ne définit `FASTRTPS_DEFAULT_PROFILES_FILE`,
  `RMW_IMPLEMENTATION`, `ROS_LOCALHOST_ONLY` ; toutes posent seulement
  `ROS_DOMAIN_ID=28`.
- Conclusion : la mémoire partagée est active, par défaut. L'audit (S13) la
  croyait absente. Reste non observé : la liste des segments réellement
  attachés à un processus (nécessite `lsof`/root) — `[NON OBSERVÉ]`.

## M02 — Le trafic image passe-t-il par la radio ?

- Commandes : `/sys/class/net/{wlP1p1s0,lo}/statistics/{tx,rx}_bytes` avant et
  après 10 s ; `ros2 topic echo /wrist_camera/image_raw --once --field …` ;
  `ros2 topic hz /wrist_camera/image_raw`.
- Résultat : Wi-Fi TX 2 506 118 340 → 2 506 158 986 (+40 646 o en 10 s, soit
  4 065 o/s) ; RX +20 319 o (2 032 o/s). Boucle locale : +373 719 288 o
  (37,4 Mo/s). Image : 640×480, `yuv422_yuy2`, pas de 1 280 o, 30,0 Hz mesurés
  → 18,4 Mo/s (147 Mbit/s).
- Conclusion : le Wi-Fi porte 0,02 % du débit de l'image. Le trafic image circule
  sur la boucle locale ; les 37,4 Mo/s s'expliquent par l'image livrée à deux
  abonnés (facteur ~2). **L'affirmation S15 « les images passent par le Wi-Fi »
  est réfutée.**

## M03 — Exposition réseau du domaine 28

- NON MESURÉ. Exige un second poste sur le même réseau, fourni par l'opérateur.
  Aucune conclusion n'est tirée ; l'hypothèse reste ouverte pour P16.

## M04 — Le pilote arrête-t-il les moteurs sans consigne ?

- Commandes : `systemctl cat ros2-driver-node`, `python3 -c "import Rosmaster_Lib…"`,
  lecture de `Mcnamu_driver_X3.py` (copie déployée du workspace vendor) et de
  `Rosmaster_Lib/Rosmaster_Lib.py` dans l'egg 3.3.9.
- Résultat : l'unité lance `ros2 run yahboomcar_bringup Mcnamu_driver_X3` depuis
  `/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws`. Le nœud s'abonne à
  `cmd_vel_safe` (profondeur 1, ligne 80) ; `cmd_vel_callback` (l. 104-122)
  applique rampe, bande morte et butées puis appelle `set_car_motion`. Le timer
  de 0,1 s (l. 95) appelle `pub_data`, qui ne publie que de la télémétrie
  (`vel_raw`, `odom_raw`, `imu/data_raw`, `imu/mag`) : aucun ordre moteur.
  `set_car_motion` (l. 558-580) écrit une trame unique sur le port série, sans
  minuterie ni garde ; aucune occurrence de `timeout`, `watchdog`, `heartbeat`
  dans la bibliothèque (hors boucles de calibration des servos).
- Conclusion : **aucun arrêt sur silence côté logiciel**. Si l'arbitre cesse de
  publier `cmd_vel_safe`, le MCU conserve la dernière consigne. Un éventuel
  watchdog de firmware n'est pas observable en lecture seule — `[NON OBSERVÉ]`.

## M05 — Qui ouvre le port série ?

- Commandes : `ls -l /dev/serial/by-id/`, `ls -l /dev/ttyUSB* /dev/ttyACM* /dev/myserial`,
  `fuser -v` par device, `grep` sur `hardware_service.py`.
- Résultat :
  - `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` → `ttyUSB0`, propriétaire
    unique `Mcnamu_driver_X3` (PID 3115) ;
  - `/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0`
    → `ttyUSB1`, propriétaire unique `ydlidar_ros2_driver_node` (PID 3614) ;
  - `/dev/myserial` est un lien vers `ttyUSB0` (même propriétaire) ;
  - `hardware_service.py` ne contient ni `Rosmaster`, ni `serial.Serial`, ni
    `/dev/tty` : il ne touche pas au série.
- Conclusion : un seul propriétaire par périphérique, conformément à l'invariant
  du référentiel. Le chemin stable du MCU est `usb-1a86_USB_Serial-if00-port0`.

## M06 — Topologie USB

- Commandes : `lsusb -t`, `lsusb`, `udevadm info -q property -n /dev/videoN`.
- Résultat : le bus 3 (`tegra-xusb`, 10 000 Mb/s → hubs 5 000 Mb/s) ne porte
  aucun périphérique. L'Astra (`2bc5:050f` caméra, `2bc5:060f` capteur de
  profondeur) est sur le bus 1 à **480 Mb/s**, derrière deux concentrateurs VIA
  imbriqués ; deux « USB Billboard Device » (`2109:8817`) signalent un lien
  USB-C négocié en USB 2.0. La caméra du poignet (Sonix `0c45:6340`) partage le
  même bus, sur le hub Genesys `05e3:0608`. Le MCU (`1a86`, ch34x) et le lidar
  (CP2102) sont aussi sur ce bus, en 12 Mb/s.
- Conclusion : l'Astra est en USB 2.0, pas en USB 3.0. À 480 Mb/s (60 Mo/s
  théoriques) et 36,9 Mo/s bruts pour profondeur + couleur à 30 Hz, la marge est
  faible ; le partage de hub avec la caméra du poignet est un facteur de perte
  d'images à examiner en P11.

## M07 — Charge CPU instantanée

- Commandes : `top -b -n 3 -d 2 -p <19 pids>` (pidstat absent), puis delta de
  `/proc/stat` sur 3 s pour la charge par cœur.
- Résultat (instantané, %CPU) : astra 35,5 · yolo 19,5 · arbitre 14,5 ·
  pilote 13,0 · rosbridge 10,0 · oled 9,5 · directeur 7,0 · hardware_service 6,0 ·
  lidar 5,5 · caméra poignet 4,5 · joint_state_publisher 4,5 · ekf 3,0 ·
  slam 2,0 · sentinelle 2,0. Somme ≈ 142 % des 8 cœurs.
  Par cœur : cpu0 27,4 · cpu1 24,1 · cpu2 23,7 · cpu3 23,1 · **cpu4 22,1** ·
  cpu5 24,1 · cpu6 23,4 · cpu7 24,0.
- Conclusion : les moyennes de `ps` (S12 : astra 57,2 %, yolo 10,3 %) ne décrivent
  pas la charge du moment. Le cœur le moins chargé est cpu4.

## M08 — Ports en écoute

- Commandes : `ss -ltnp`, `ss -uanp | grep -E ":74[0-9][0-9]"`.
- Résultat : 8000 `api_server` (pont C++), 8001 `hardware_service`,
  8003 `yolo_service`, 8080 `mkdocs serve`, 9090 `rosbridge_websocket`,
  8888 et 8889 (Jupyter), 8081, 8644 (passerelle Hermes), 22, 111, 631, 3389 ;
  tous sur `0.0.0.0`/`*` sauf 11434, 11539, 60589 et 53 (boucle locale).
  Aucune écoute UDP dans la plage 74xx (domaine DDS découvert par multicast sur
  d'autres ports).
- Conclusion : les trois services du robot (8000, 8001, 8003) et le pont web
  (9090) sont joignables depuis le réseau, sans authentification observée à ce
  niveau. Élément pour P16.

## M09 — Intentions des trois éditeurs de `/cmd_vel`

- Commandes : lecture de `ros2_llm_bridge/hardware_service.py`,
  `ros2_llm_bridge_cpp/src/bridge_node.cpp`, `clawbot_sentinel/.../sentinel_node.py`.
- Résultat :
  - `hardware_service.py` : publie sur `POST /motion` (l. 318-320) après
    écrêtage (`MAX_LINEAR_MS=0.5`, `MAX_ANGULAR_RS=1.5`) et contrôle lidar ;
    sur `POST /motion/stop` (l. 339) une consigne nulle immédiate ; et par un
    fil de surveillance (l. 190-200) qui publie une consigne nulle toutes les
    0,3 s dès que 1,5 s se sont écoulées sans mouvement. Rythme : à la demande,
    plus un zéro périodique.
  - Pont C++ : n'écrit que dans le chemin de secours de `Stop` quand le service
    8001 est injoignable (l. 94-97) — consigne nulle unique.
  - Sentinelle : publie une consigne nulle uniquement lors d'un arrêt local
    (mot « arrête », `arreter_localement`), jamais en continu ; elle ne publie
    jamais sur `/cmd_vel_safe`.
- Conclusion : aucun des trois n'entretient une consigne non nulle sans
  nouvelle demande. Le watchdog de `hardware_service` (1,5 s) est le seul arrêt
  automatique existant, et il ne couvre que les consignes qu'il a lui-même
  émises.

## M10 — Outils MCP existants

- Commandes : lecture de `bridge_mcp/tools.py`, `bridge_mcp/ros_layer.py`,
  `~/.hermes/config.yaml`.
- Résultat : 25 outils déclarés. Par cible :
  - lecture ROS 2 : `graph_snapshot`, `tf_snapshot`, `topic_stats`, `param_get`,
    `param_list`, `goal_list`, `goal_send`, `safety_stop` ;
  - directeur S1 (`/director/command`) : `get_task`, `start_skill`,
    `cancel_task` (et `goal_send` en amont) ;
  - état/journal du pont : `incident_list`, `incident_get`, `diagnostics`,
    `logs_tail`, `audit_tail`, `resources_snapshot`, `capabilities`, `escalate` ;
  - écritures contrôlées : `param_set`, `param_restore` (liste blanche et
    bornes), `patch_propose`, `spec_propose` (dépôt, sans build), `test_run`
    (pytest isolé).
  Le serveur est déclaré dans `~/.hermes/config.yaml` — `command:
  /usr/bin/python3`, `args: [-m, bridge_mcp.stdio]`, `PYTHONPATH=/home/jetson/clawbot`,
  `ROS_DOMAIN_ID=28`. Hermes tourne donc **sur le Jetson**, en `stdio`.
- Conclusion : aucun outil MCP ne passe par HTTP 8000/8001 depuis le poste
  distant ; le transport est local. P10 peut conserver `stdio`.

## M11 — Pourquoi le bras, MoveIt et Nav2 ne tournent pas

- Commandes : `systemctl status|is-enabled|cat`, `journalctl -u … -n 80`,
  `systemctl show -p ActiveEnterTimestamp -p ConditionResult`.
- Résultat : les trois unités sont activées (`linked`, `linked`, `enabled`),
  `ActiveState=inactive`, `ActiveEnterTimestamp=n/a`, `Result=success`,
  journaux vides sur 30 jours, `ConditionResult=no` sans directive `Condition`
  dans les fichiers. Le fichier de `clawbot-move-group` porte le commentaire
  « unité optionnelle : ne démarre pas au boot », alors qu'elle est activée.
- Conclusion : elles n'ont pas échoué — elles n'ont jamais été démarrées. Le
  commentaire et l'état d'activation se contredisent ; `ConditionResult=no`
  n'est pas interprété comme un échec (systemd le rapporte aussi pour une unité
  jamais évaluée) — `[À VÉRIFIER]` en P13.

## M12 — Comment l'Astra est lancée

- Commandes : lecture de `hardware_service.py`, `ros2 param get /camera/camera`,
  `journalctl -k --since "-7d"`.
- Résultat : `hardware_service.py` ne lance **pas** `astra_camera` ; il capture
  des images par index OpenCV (`CAMERA_DEVICES`). Le lancement est assuré par
  `orbbec-camera.service` (activée, démarrée le 2026-11-12), via `ros2 launch`.
  Paramètres : `depth_fps=30`, `color_fps=30`, `depth_width=640`,
  `depth_height=480`, `enable_depth=true`, `enable_color=true` ; `uvc_video_dev`
  et `depth_mode` non définis. Noyau : deux lignes `tegra-xusb 3610000.usb:
  ERROR unknown event type 37` (22/11 07:38 et 10:02), aucune erreur `uvcvideo`
  ni `astra`.
- Conclusion : profondeur 640×480 à 30 Hz, couleur 640×480 à 30 Hz, les deux
  actives — soit ~36,9 Mo/s bruts sur un lien USB 2.0 partagé (M06). Les deux
  erreurs `tegra-xusb` sont des événements de contrôleur, pas des erreurs de
  flux ; à surveiller en P11.

## M13 — Deux éditeurs sur `/joint_states`

- Commandes : `ros2 topic info -v /joint_states`, `ros2 topic echo --once`
  (boucle pour distinguer les éditeurs), `ros2 topic hz`, lecture du pilote.
- Résultat : deux éditeurs déclarés (`driver_node`, `joint_state_publisher`) et
  un abonné (`robot_state_publisher`), tous RELIABLE/VOLATILE. Cadence mesurée :
  20,0 Hz, soit le seul `joint_state_publisher` (`rate=20`). Ses messages
  portent 15 joints — `arm_joint1…5`, `grip_joint`, `rlink_joint2/3`,
  `llink_joint1/2/3`, `front_left_joint`, `front_right_joint`, `back_left_joint`,
  `back_right_joint` — tous à `0.0`, avec `velocity: []` et `effort: []`.
  Le pilote, lui, crée l'éditeur (l. 88), remplit `state.name` avec six roues
  (l. 177-182) mais **n'appelle jamais `publish`** sur cet éditeur : aucun
  message de sa part sur le topic.
- Conclusion : un éditeur mort. Les positions articulaires réelles du bras ne
  sont jamais publiées ; `robot_state_publisher` calcule les TF du bras sur des
  zéros et les roues n'ont aucune TF mobile. Les deux sources ne se contredisent
  pas sur le fil (une seule publie), mais l'état publié contredit le matériel.

## Incertitudes restantes

| Question | Statut | Commande qui trancherait |
|---|---|---|
| Segments `fastrtps_*` réellement attachés | `[NON OBSERVÉ]` | `sudo lsof /dev/shm/fastrtps_*` |
| Watchdog de firmware du MCU | `[NON OBSERVÉ]` | essai matériel : couper `cmd_vel_safe` robot sur cales (P03) |
| Visibilité du domaine 28 depuis le réseau | `[NON MESURÉ]` | M03 depuis un second poste |
| `ConditionResult=no` des trois unités | `[À VÉRIFIER]` | `systemctl show -p Condition*` après un `start` refusé (P13, avec accord) |

## Décisions pour la suite

| Décision | Valeur constatée | Effet sur les prompts |
|---|---|---|
| Délai d'arrêt du pilote | **Absent** : aucune garde dans le nœud ni dans `Rosmaster_Lib` ; `set_car_motion` écrit une trame unique (M04) | P03 : à ajouter ou à paramétrer |
| Chemin `by-id` du MCU | `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` (M05) | P03 : valeur par défaut de `device_path` |
| Propriétaires du port série | 1 par device : PID 3115 (châssis) sur `ttyUSB0`, PID 3614 (lidar) sur `ttyUSB1` ; `hardware_service` n'y touche pas (M05) | P03 : rien à retirer |
| SHM active, trafic image sur la radio | SHM **oui** (85 segments, 11 Mo) ; Wi-Fi 4,1 ko/s face à 18,4 Mo/s d'image → trafic local (M01, M02) | P16 : priorité **basse** |
| Lieu d'exécution de Hermes | Jetson, `stdio` (`/usr/bin/python3 -m bridge_mcp.stdio`, domaine 28) (M10) | P10 : transport `stdio` |
| Cœur le moins chargé | cpu4 (22,1 %), puis cpu3 (23,1 %) et cpu6 (23,4 %) (M07) | P04 : `CPUAffinity` de l'arbitre = 4 |
| Cause de l'arrêt du bras et de MoveIt | Jamais démarrées (`ActiveEnterTimestamp=n/a`, journaux vides, `Result=success`) bien qu'activées ; aucune erreur (M11) | P13 : décider si elles démarrent au boot |
| Paramètres et erreurs USB de l'Astra | 640×480@30 profondeur et couleur, tout activé ; Astra en **USB 2.0** derrière deux hubs VIA ; 2 erreurs `tegra-xusb`, aucune erreur `uvc` (M06, M12) | P11 : priorité haute sur le lien USB |
| Éditeurs de `/joint_states` | 2 déclarés, 1 seul publie (`joint_state_publisher`, 20 Hz, 15 joints à 0,0) ; éditeur du pilote mort (M13) | P13 : réparer ou supprimer l'éditeur du pilote |
