---
title: "Audit d'inventaire du poste et nettoyage de palier 1 — 2026-11-22"
date: "2026-11-22T10:47:19+01:00"
author: "Hermes Agent"
tags: [operations, inventaire, disque, systemd, docker, doublons, nettoyage, maintenance]
status: validé
---

# Audit d'inventaire du poste et nettoyage de palier 1 — 2026-11-22

Classement de `/home/jetson` en quatre catégories (actif, utilisable, doublon, inutile) établi sur
preuves, puis exécution du palier 1 annoncé. Retour à l'[[index]]. Topologie des unités :
[[systemd_robot_services]] ; graphe ROS 2 : [[ros2_graph_clawbot]].

## 1. Méthode et état du disque

La vérité terrain retenue est celle des `ExecStart`, `WorkingDirectory` et `Environment` des unités
systemd actives, recoupée par les imports Python, les empreintes MD5 des fichiers de plus de 5 Mio et
les dates de dernière modification (`/` est monté en `relatime`, l'`atime` n'est pas exploitable).

État relevé le 2026-11-22T10:13:37+01:00, commande `df -h /` :

| Grandeur | Valeur |
|---|---|
| Partition racine | 147 Gio, **120 Gio utilisés, 21 Gio libres (86 %)** |
| `/var` | 50 Gio (dont Docker) |
| `/usr` | 36 Gio |
| `/home/jetson` | 26 Gio |
| `/opt` | 4,6 Gio |

Le home ne reconstitue pas le `df` : le premier gisement est `/var/lib/docker` (`docker info`,
`Docker Root Dir: /var/lib/docker`), hors du home.

## 2. Activement utilisé — 16 unités à l'état `running`

| Unité | Chemin exécuté | Taille |
|---|---|---|
| `clawbot-description` | `clawbot/launch/robot_description.launch.py`, `CLAWBOT_URDF=clawbot/urdf/clawbot_x3plus.urdf` | — |
| `clawbot-director` | `clawbot/install/setup.bash` + `clawbot_director.director_node` | — |
| `clawbot-safety-arbitrator` | `clawbot/install/setup.bash` + `clawbot_safety.arbitrator` | — |
| `clawbot-sentinel` | `clawbot/install/setup.bash` + `clawbot_sentinel.sentinel_node` | — |
| `clawbot-docs` | `~/.local/bin/mkdocs serve`, port 8080 | — |
| `clawbot-ekf` | `yahboomcar_ros2_ws/software/library_ws/install/robot_localization/lib/ekf_node` | — |
| `clawbot-lidar` | `library_ws/install` + YDLIDAR TG30 | — |
| `orbbec-camera` | `library_ws/install` + `astra_camera astro_pro_plus.launch.xml` | — |
| `ros2-driver-node` | `yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash` + `ros2 run yahboomcar_bringup Mcnamu_driver_X3` | — |
| `ros2-hardware-service` | `clawbot/ros2_llm_bridge/hardware_service.py`, port 8001 | — |
| `ros2-llm-bridge-cpp` | `clawbot/install/ros2_llm_bridge_cpp/lib/ros2_llm_bridge_cpp/api_server`, port 8000 | — |
| `rosbridge` | `yahboomcar_ws/install/setup.bash` + `rosbridge_websocket`, port 9090 | — |
| `yolo-inference` | `~/yolov5_env/bin/python3 clawbot/yolo_service.py`, modèle `software/yolov5-7.0/yolov5s.pt` | — |
| `yahboom_oled` | `python3 /home/jetson/oled_yahboom/yahboom_oled.pyc` | — |
| `clawbot-slam` | `ros2 run slam_toolbox async_slam_toolbox_node` | — |
| `clawbot-wrist-camera` | `ros2 run v4l2_camera` + `clawbot/config/wrist_camera_info.yaml` | — |

Trois environnements Python coexistent et sont tous consommés : `/usr/bin/python3` avec `~/.local`
(308 paquets, ROS 2 et scripts des unités), `~/yolov5_env` (2,9 Gio, seul consommateur d'inférence),
venv Hermes (Python 3.14, agent seulement). Le lien `/Robot_Knowledge_Base` est un symlink vers
`clawbot/docs/knowledge-base` : 0 octet `du`, contenu réel 692 Kio.

Activées mais arrêtées, donc « utilisables » : `clawbot-nav2`, `clawbot-arm-controller`,
`clawbot-move-group`, `clawbot-joy-teleop`, `clawbot-health`, `ros2-llm-bridge` (docker compose).

## 3. Utilisable sous condition

| Élément | Taille | Raison de non-classement en « inutile » |
|---|---|---|
| `ultralytics/ultralytics/data/yahboom_data` | 899 Mio | seul jeu d'entraînement du poste (vidéo `orange.mkv` 125 Mio comprise) ; réentraînement non tranché |
| `software/yolov5-7.0` hors `yolov5s.pt` | 657 Mio | `runs/train` 259 Mio, 4 `*.wts` 250 Mio, 2 `*.onnx` 56 Mio, `best.pt`/`last.pt` |
| `~/.local/.../pypinyin_dict` | 734 Mio | installé en `--user`, aucun script du poste n'importe `pypinyin` (seul `pypinyin` lui-même le fait) |
| `~/.local/.../torch` | 593 Mio | aucun import hors `torchx`/`ray` ; l'inférence utilise `yolov5_env` |
| `~/.cache/ms-playwright` | 327 Mio (après nettoyage) | aucune installation `playwright` en `--user` ; outil navigateur de l'agent servi par `~/.hermes/tools` |
| `~/.vscode-server` | 635 Mio | deux serveurs `Stable-*` (7d842fb8, 03c265b1) et `copilot-chat` 0.32.3 + 0.32.4 |
| `~/.gemini` | 398 Mio | CLI Gemini et Antigravity, dernière écriture 2026-11-18 |
| `~/.cache/uv` 300 Mio, `jedi` 170 Mio, `electron` 111 Mio | 581 Mio | caches reconstructibles |
| `joycond`, `dkms-hid-nintendo` | 3,9 Mio | manette Nintendo ; `joycond.service` **disabled** |

## 4. Doublons

### 4.1 Trois exemplaires des paquets vendor Yahboom

`~/yahboomcar_ros2_ws/yahboomcar_ws/src/` · `~/clawbot/` · et leurs `build/install` respectifs.
`diff -rq` par paquet, `clawbot` contre `yahboomcar_ws/src` :

| Résultat | Paquets |
|---|---|
| 0 différence | 19 paquets (`yahboomcar_astra`, `_base_node`, `_ctrl`, `_KCFTracker`, `_linefollow`, `_mediapipe`, `_msgs`, `_multi`, `_nav`, `_point`, `_rviz`, `_slam`, `_visual`, `_voice_ctrl`, `yahboom_app_save_map`, `yahboom_web_savmap_interfaces`, `laserscan_to_point_pulisher`, `robot_pose_publisher_ros2`) |
| divergents | `yahboomcar_description` (35 fichiers), `yahboomcar_bringup` (1), `yahboomcar_laser` (1) |

Aucun service actif n'importe `yahboomcar_msgs` : la copie de `clawbot` compile 21 paquets vendor que
personne ne consomme à l'exécution. Le doublon réel est l'arbre source présent dans deux `src/`.

### 4.2 Fichiers identiques (empreinte vérifiée sur les 2 premiers Mio + taille)

| Fichier | Copies | Empreinte | Perte |
|---|---|---|---|
| `yahboomcar_slam/params/ORBvoc.txt` | 4 (2 `src/`, 2 `install/`) | identique | 415 Mio |
| `shape_predictor_68_face_landmarks.dat` | 3 | identique | 190 Mio |
| `frozen_inference_graph.pb` | 2 | identique | 66 Mio |
| `chromium-1208/chrome-linux/chrome` | 2 (`~/.cache/ms-playwright`, `~/.hermes/tools`) | `8e0937ee1e3e3fc3312f146ea0a61010` | 428 Mio |
| `librl_lib.so` | 2 (`build/` + `install/`) | identique | 148 Mio |

Total mesuré des doublons de plus de 5 Mio : **1,56 Gio**.

### 4.3 Rôles dupliqués

| Rôle | Exemplaires | État mesuré |
|---|---|---|
| Interface web de supervision | `charles_dashboard` (conteneur `charles_robot_suite-charles-dashboard-1`, port 8081), `clawbot_monitoring` (image `clawbot-clawbot_monitoring`, jamais lancée), `robot_app`, `robot_gui` | conteneur `Up`, `ROS_DOMAIN_ID=0` contre 28 pour la pile ; autostart `start_app.sh.desktop` avec `Hidden=true` et `X-GNOME-Autostart-enabled=false` |
| Image du pont LLM | `clawbot-llm_bridge:latest` 857 Mo et `ros2_llm_bridge-llm_bridge:latest` 753 Mo | même service, deux builds |

## 5. Inutile

| Élément | Taille | Preuve |
|---|---|---|
| `JEP` | 1,35 Gio | clone du 2024-11-13, `script/workspace/opencv-4.10.0` 1,1 Gio ; aucune unité ne le cite |
| `Rosmaster` | 0,61 Gio | démos vendor, dernière modification 2025-06-25, autostart désactivé |
| `Pytorch_demo` + `TensorFlow_demo` | 0,54 Gio | février 2025, dont `cifar-10-python.tar.gz` 163 Mo |
| `mediapipe` (racine) | 97 Mio | copie de `shape_predictor_68_face_landmarks.dat` déjà présent dans le paquet ROS |
| `KNN`, `opencv`, `qr_code_recognition`, `jps`, `py_installv0.02`, `.ipynb_checkpoints`, `share` | 5 Mio | tutoriels vendor |
| `~/.ros/log` | 1,25 Gio | 3 847 fichiers ; un seul journal `astra_camera_node_107658_1772656796521.log` = 1 115 Mio |
| `yahboomcar_ros2_ws/software/library_ws/build` | 1,24 Gio | build intermédiaire ; seul `install/` est exécuté |
| `yahboomcar_ros2_ws_yahboomcar_ws` | 14 Mio | copie imbriquée (`ws/ws/ws`), jamais référencée |
| `snapd_24724.snap` + `.assert` | 46 415 872 octets | téléchargement snap de février 2026 |
| `start_ros_robot.sh`, `start_slam.sh`, `start_clawbot.sh` | — | sourcent `/home/jetson/yahboomcar_ros2_ws/install/setup.bash`, `ENOENT` (le chemin réel contient `yahboomcar_ws/`) et forcent `ROS_DOMAIN_ID=0` |
| Images Docker legacy | 33,5 Gio | `ros-noetic:3.0.5` 14,9 Gio, `ros-foxy-orbslam2:1.0.0` 10,9 Gio, `tiryoh/ros2-desktop-vnc:foxy` 7,75 Gio ; `docker system df` : 34,94 Gio d'images, **26,77 Gio récupérables (76 %)** |

## 6. Palier 1 exécuté

| Action | Commande | Résultat mesuré |
|---|---|---|
| Journaux ROS de plus de 24 h | `find .ros/log -type f -mtime +0 -delete` | 1 232 Mio libérés, reste 48 Mio |
| Build `library_ws` | `rm -rf yahboomcar_ros2_ws/software/library_ws/build` | 1,3 Gio ; `install/setup.bash` intact (13 août 2025) |
| Build `yahboomcar_ws` | `rm -rf yahboomcar_ros2_ws/yahboomcar_ws/build` | 118 Mio ; `install/setup.bash` intact (11 nov. 12:08) |
| Doublon navigateur | `rm -rf .cache/ms-playwright/chromium-1208` | 428 Mio ; outil navigateur vérifié avant et après |
| Résidus | `rm -f snapd_24724.snap snapd_24724.assert robot_start.log clawbot.log ros_launch.log` | 51 Mio |
| Reconstruction `clawbot` | `sudo systemctl stop clawbot-director clawbot-safety-arbitrator clawbot-sentinel ros2-llm-bridge-cpp` puis `sudo rm -rf build install log`, `unset VIRTUAL_ENV PYTHONPATH PYTHONHOME`, `PATH=/usr/bin:/bin:/usr/sbin:/sbin`, `source /opt/ros/humble/setup.bash`, `colcon build` | **38 paquets terminés en 2 min 32 s, code retour 0** ; `install/setup.bash` recréé à 10:16 |

Les quatre unités arrêtées sont passées en `failed` (comportement attendu) : `reset-failed` puis
redémarrage dans l'ordre `ros2-llm-bridge-cpp`, `clawbot-safety-arbitrator`, `clawbot-sentinel`,
`clawbot-director`.

## 7. Vérifications après nettoyage

Relevés de 10:17 à 10:19, domaine 28.

| Contrôle | Commande | Valeur |
|---|---|---|
| Unités actives | `systemctl list-units --type=service --state=running` | **16 / 16** |
| Topics | `ros2 topic list \| wc -l` | **54** (54 avant nettoyage) |
| Nœuds | `ros2 node list \| wc -l` | 20 |
| Tension | `ros2 topic echo /voltage --once` | `11.899999618530273` |
| Directeur | `ros2 topic echo /director/state --once` | `{"state": "IDLE", "task_id": null, ...}` |
| Pont C++ | `curl 127.0.0.1:8000/health` | `{"status":"healthy"}` |
| YOLO | `curl 127.0.0.1:8003/health` | `{"status":"ok","model_loaded":true,"device":"cuda"}` |
| Site | `curl 127.0.0.1:8080/` | `200` |
| Suite de tests | `scripts/run_tests.sh tests --ignore=tests/test_cpp_bridge.py --ignore=tests/test_modes.py` | **238 passed, 1 skipped, 19 errors, 49,62 s** |

Les 19 erreurs sont toutes dans `tests/test_regression.py` (`def test_x(args)` interprété comme une
fixture) et sont antérieures au nettoyage. `tests/test_cpp_bridge.py` et `tests/test_modes.py` ne sont
pas des tests pytest : ils appellent `localhost:8002` à l'import et échouent à la collecte.
`scripts/run_tests.sh` sans argument collecte le dépôt entier et rend 72 erreurs dans les paquets
vendor : le chemin `tests` est obligatoire.

| Grandeur | Avant | Après |
|---|---|---|
| Racine utilisée | 120 Gio | 117 Gio |
| Racine libre | 21 Gio (86 %) | **24 Gio (84 %)** |
| `/home/jetson` | 26 Gio | 23 Gio |

## 8. Ce qui reste à trancher

| Palier | Contenu | Gain estimé |
|---|---|---|
| 2 | démos vendor (JEP, Rosmaster, TensorFlow/Pytorch_demo, mediapipe, excédent yolov5) et images Docker legacy | 4,4 Gio + 26,77 Gio |
| 3 | `pypinyin_dict`, `torch` en `--user`, `.gemini`, vieux serveur VS Code | 2,7 Gio |

Décisions ouvertes : supprimer la copie vendor de `clawbot` et patcher le seul arbre `yahboomcar_ws`,
ou l'inverse ; conserver **une** interface web sur les quatre ; supprimer les deux images du pont LLM
au profit de l'unité `ros2-llm-bridge-cpp` déjà en service.

## Voir aussi

- [[index]]
- [[systemd_robot_services]]
- [[ros2_graph_clawbot]]
- [[etat_noeuds_et_services]]
- [[jetson_orin_nx]]
- [[ERR-2026-11-10-002_espace_disque_critique]]
- [[llm2ros_bridge]]
- [[documentation_constructeur_yahboom]]
