# Inventaire du démarrage — P14 (à valider avant tout déplacement)

**Date :** 2026-11-22 · **Branche :** `refactor/REQ-OPS-040-demarrage`
**Statut : proposition — rien n'a été déplacé, supprimé ni déployé.**
Mesures : `systemctl cat/show`, `ros2 node list`, `ros2 topic info -v`, `ss -tnp`,
`journalctl`, `colcon list`, `grep -rn`.

## 0. Ce que la mesure corrige dans le prompt

| Prémisse | Mesure du 2026-11-22 | Conséquence |
|---|---|---|
| « 38 paquets » | **46** paquets `colcon` | le plan de nettoyage porte sur 46 |
| « 27 launch files » | **27** confirmé, dont 21 jamais lancés par une unité |
| « 14 unités systemd » | **26** fichiers dans `services/` + 2 dans `systemd/`, 28 unités `clawbot*`/`ros2-*` dans `/etc` | l'inventaire ci-dessous les couvre toutes |
| « 20 nœuds » | **23** entrées `ros2 node list`, dont **15 applicatifs** (voir §6) | O11 est déjà tenu sous cette définition, à confirmer |
| `rosbridge` exposé, 9,9 % CPU | **0 connexion** en 7 jours (`journalctl -u rosbridge`), aucune socket sur 9090 | décision Q11 simplifiée |
| docs « serveur de développement » | déjà lié à `127.0.0.1:8080` (`mkdocs serve --dev-addr`) | Q12 = sortir du mode *dev*, pas de l'exposition |

**Défaut supplémentaire trouvé :** `clawbot-lidar.service` existe **deux fois** dans le
dépôt, avec des contenus différents — `systemd/clawbot-lidar.service` (déployé, passe
`params_file:=config/ydlidar_x3plus.yaml`) et `services/clawbot-lidar.service` (variante
sans `params_file`, donc `frame_id` non aligné sur l'URDF). `/etc` pointe sur `systemd/`.
Relier la mauvaise copie casse `/scan` sans erreur visible. C'est la « double
description » au sens littéral.

## 1. Unités → un fichier de lancement par unité

Cible : `ros2 launch clawbot_bringup <fichier>.launch.py`, paramètres lus par
`get_package_share_directory`, `ROS_DOMAIN_ID` dans `deploy/env/clawbot.env`.

| Unité | État | ExecStart actuel (résumé) | Cible | Décision |
|---|---|---|---|---|
| `ros2-driver-node` | active | `ros2 run clawbot_base_driver driver_node` | `base.launch.py` | réécrite |
| `clawbot-lidar` | active | `ros2 launch ydlidar_ros2_driver` (systemd/, avec `params_file`) | `lidar.launch.py` | réécrite, **doublon `services/` supprimé** |
| `ros2-hardware-service` | active | `python3 ros2_llm_bridge/hardware_service.py` | `hardware.launch.py` | réécrite (HTTP 8001) |
| `clawbot-ekf` | active | binaire vendor `ekf_node --params-file config/ekf.yaml` | `localization.launch.py` | réécrite |
| `clawbot-slam` | active | `ros2 run slam_toolbox async_slam_toolbox_node …` | `mapping.launch.py` | réécrite, **capacité `mapping`** (pas `always_on`) |
| `clawbot-description` | active | `ros2 launch /home/jetson/clawbot/launch/robot_description.launch.py` | `description.launch.py` | réécrite |
| `clawbot-safety-arbitrator` | active | `python3 -c '… arbitrator …'` | `safety.launch.py` | réécrite |
| `clawbot-capability-manager` | active | binaire `gestionnaire` | `capabilities.launch.py` | réécrite |
| `clawbot-skill-server` | active | binaire `skill_server` | `executive.launch.py` | réécrite |
| `clawbot-mission-executive` | inactive | binaire `mission_executive` | `mission.launch.py` | réécrite, démarrée par la cible |
| `clawbot-director` | active | `python3 -c '… director_node …'` + `ExecStop` script | `director.launch.py` | réécrite (le `ExecStop` reste sur l'unité) |
| `clawbot-sentinel` | active | `python3 -c '… sentinel_node …'` | `sentinel.launch.py` | réécrite, **sonde de flux retirée** (§7) |
| `clawbot-health-monitor` | active | binaire `health_monitor` | `health.launch.py` | réécrite |
| `clawbot-wrist-camera` | active | `ros2 run v4l2_camera …` | `wrist_camera.launch.py` | réécrite |
| `orbbec-camera` | active | `ros2 launch astra_camera astro_pro_plus…` (overlay vendor) | `depth_camera.launch.py` | réécrite ; **dépend de l'overlay vendor** `yahboomcar_ros2_ws/software/library_ws` |
| `clawbot-yolo` | active | `/home/jetson/yolov5_env/bin/python3 -m yolo_node.noeud` | `detection.launch.py` | réécrite ; le lancement doit garder le **python du venv** |
| `ros2-llm-bridge-cpp` | active | binaire `api_server`, `HARDWARE_SERVICE_URL` | `api.launch.py` | réécrite, **routes de mouvement rebranchées** (§4) |
| `clawbot-arm-controller` | inactive | `ros2 launch clawbot_arm_controller …` | `arm_controller.launch.py` | réécrite, à la demande (capacité) |
| `clawbot-move-group` | inactive | `ros2 launch clawbot_moveit_config …` | `move_group.launch.py` | réécrite, à la demande |
| `clawbot-nav2` | inactive | `ros2 launch /home/jetson/clawbot/launch/navigation.launch.py` | `navigation.launch.py` | réécrite, à la demande |
| `clawbot-joy-teleop` | inactive | script `joy_teleop_wait.sh` | `teleop.launch.py` | réécrite, à la demande |
| `rosbridge` | active | `ros2 launch rosbridge_server` | — | **supprimée si Q11 = retrait** |
| `clawbot-docs` | active | `mkdocs serve --dev-addr 127.0.0.1:8080` | — (hors ROS) | **Q12** : build statique servi sur `127.0.0.1` |
| `yahboom_oled` | active | `python3 /home/jetson/oled_yahboom/yahboom_oled.pyc` | — | **conservée hors cible** : code hors dépôt, aucun nœud ROS |
| `clawbot-health` | active | oneshot Telegram (`bridge_mcp.health --notify`) | — | **conservée hors cible** (nom déjà pris, cf. P07) ; dépend de `bridge_mcp` → à rebrancher sur `clawbot_mcp` sinon supprimée |
| `yolo-detector` | inactive | ancien détecteur | — | **supprimée** (remplacée par `clawbot-yolo`) |
| `yolo-inference` | inactive | ancien détecteur | — | **supprimée** |
| `ros2-llm-bridge` | inactive | API python | — | **supprimée** (remplacée par le C++) |

Résultat : **21 unités** (20 ROS + docs) sous `clawbot.target`, 2 hors cible
(`yahboom_oled`, `clawbot-health`), 4 supprimées.

## 2. Fichiers de lancement (27) → 21 cibles, 21 supprimés

| Conservés, déplacés dans `clawbot_bringup` | Origine |
|---|---|
| `base`, `lidar`, `hardware`, `localization`, `mapping`, `description`, `safety`, `capabilities`, `executive`, `mission`, `director`, `sentinel`, `health`, `wrist_camera`, `depth_camera`, `detection`, `api`, `arm_controller`, `move_group`, `navigation`, `teleop` | `launch/` (3), `clawbot_arm_controller`, `clawbot_moveit_config`, unités existantes |

| Supprimés (21) | Raison |
|---|---|
| `pkg_tf/launch/turtle_following.launch.py` | didacticiel |
| `yahboomcar_*` (15 fichiers : description ×6, laser ×3, astra, KCFTracker, linefollow, mediapipe, multi ×2, nav) | vendor non déployé |
| `yahboom_app_save_map` | vendor non déployé |
| `clawbot_hardware_interface` (2 : `hardware_control`, `vision_pipeline`) | paquet non déployé, aucun test ne l'utilise |
| `slam3d/launch/slam3d.launch.py` | jamais lancé, pas un paquet `colcon` |

## 3. Paquets : 46 → 15 construits

| Gardés (15) | Pourquoi |
|---|---|
| `clawbot_common`, `clawbot_interfaces`, `clawbot_safety`, `clawbot_base_driver`, `clawbot_capabilities`, `clawbot_executive`, `clawbot_director`, `clawbot_sentinel`, `clawbot_health`, `clawbot_mcp`, `clawbot_arm_controller`, `clawbot_moveit_config`, `clawbot_sim`, `ros2_llm_bridge_cpp`, `clawbot_bringup` (nouveau) | déployés ou utilisés par les tests |

| Cas particuliers | Décision |
|---|---|
| `yahboomcar_description` | **gardé** : l'URDF et les 24 maillages de collision que MoveIt charge vivent là (P13 §3 bis) |
| `yolo_node` | **gardé** : `clawbot-yolo` exécute `python -m yolo_node.noeud` |
| `yahboom_web_savmap_interfaces` | attic : n'existe que pour `yahboom_app_save_map` |

| Sous `attic/` avec `COLCON_IGNORE` (24) | Preuve `grep -rn` : 0 référence |
|---|---|
| `pkg_action`, `pkg_helloworld_py`, `pkg_interfaces`, `pkg_metapackage`, `pkg_param`, `pkg_service`, `pkg_tf`, `pkg_topic` | 0 unité, 0 code |
| `yahboomcar_astra`, `yahboomcar_base_node`, `yahboomcar_bringup`, `yahboomcar_ctrl`, `yahboomcar_KCFTracker`, `yahboomcar_laser`, `yahboomcar_linefollow`, `yahboomcar_mediapipe`, `yahboomcar_multi`, `yahboomcar_nav`, `yahboomcar_point`, `yahboomcar_rviz`, `yahboomcar_slam`, `yahboomcar_visual`, `yahboomcar_voice_ctrl`, `yahboomcar_msgs` | 0 unité, 0 code (hors `services/README.md`, documentation) |
| `clawbot_hardware_interface` | 0 référence ; ses tests C++ ont migré dans `clawbot_health` |
| `laserscan_to_point_pulisher`, `robot_pose_publisher_ros2`, `yahboom_app_save_map`, `yahboom_web_savmap_interfaces`, `slam3d` | 0 référence |
| `ros2_llm_bridge` (python) | remplacée par `ros2_llm_bridge_cpp` (REQ-OPS-043) ; **suppression**, pas attic (3 variantes d'`api_server.py`) |
| `bridge_mcp` (316 K, dossier non `colcon`) | remplacé par `clawbot_mcp` en P10 ; **suppression après rebranchement de `clawbot-health`** |

## 4. API HTTP 8000 (REQ-OPS-043)

| Implémentation | État | Sort |
|---|---|---|
| `ros2_llm_bridge_cpp/src/api_server.cpp` + `bridge_node.cpp` | **déployée** (`ros2-llm-bridge-cpp`, active) | gardée, routes de mouvement rebranchées |
| `ros2_llm_bridge/ros2_llm_bridge/api_server.py` | non déployée (unité `ros2-llm-bridge` inactive) | supprimée avec le paquet |
| `ros2_llm_bridge/build|install/…/api_server.py` | artefacts de build | supprimés avec le paquet |
| `ros2_llm_bridge_cpp/include/…/api_server.hpp` | en-tête, pas une implémentation | gardé |

Ce que fait l'API déployée aujourd'hui, et qui doit changer : `SetVelocity` appelle
`POST http://localhost:8001/motion` (le service matériel publie `/cmd_vel/teleop`), `Stop`
appelle `/motion/stop` et **publie `/cmd_vel`** quand le service ne répond pas,
`NavigateTo` fait de la **navigation à l'estime** (durées calculées, sans odométrie). Aucun
de ces trois chemins ne passe par l'exécutif : pas de journal de mission, pas de budget,
pas de précondition de bras. Cible : `/clawbot/execute_skill` (mouvement simple) et
`/clawbot/execute_mission` (enchaînement), plus aucun éditeur `Twist` dans l'API.

## 5. `/cmd_vel` hérité (REQ-OPS-044)

Mesure : `ros2 topic info -v /cmd_vel` → **1 éditeur, `llm_bridge_node`** (repli de `Stop`
quand le service matériel est injoignable), 1 abonné `safety_arbitrator` (entrée
`legacy`, priorité 10). Le retrait suit REQ-OPS-043 : d'abord l'éditeur (code API), puis
l'entrée `legacy` de l'arbitre, quand `ros2 topic info /cmd_vel` ne montre plus d'éditeur.

## 6. Nœuds (O11)

23 entrées `ros2 node list`, dont :

- **infrastructure (6)** : `robot_state_publisher`, `joint_state_publisher`,
  `launch_ros_1308`, `transform_listener_impl` ×2 — comptés à part ;
- **rosbridge (3)** : `rosbridge_websocket`, `rosapi`, `rosapi_params` — supprimés si Q11 ;
- **applicatifs (15)** : `camera/camera` (depth), `capability_manager`, `director`,
  `driver_node`, `ekf_filter_node`, `hardware_service_node`, `health_monitor`,
  `llm_bridge_node`, `safety_arbitrator`, `sentinel`, `skill_server`, `slam_toolbox`,
  `wrist_camera/camera`, `ydlidar_ros2_driver_node`, `yolo_node`.

Le seuil O11 (≤ 15) est donc **tenu sous la définition « hors infrastructure et hors
rosbridge »**. Sans Q11, il faut compter 18. La définition retenue doit être inscrite dans
le critère de REQ-OPS-045 — c'est une décision, pas une mesure.

## 7. Sentinel

`clawbot_sentinel` sonde aujourd'hui la fraîcheur de chaque flux ; `clawbot-health-monitor`
publie déjà `/clawbot/health`. Proposition : le sentinel lit `/clawbot/health` et perd sa
sonde (un seul propriétaire de la mesure, un abonnement de moins par nœud).

## 8. Q11 — rosbridge (9090)

Usage mesuré : **0 connexion client en 7 jours**, aucune socket établie sur 9090, 3 nœuds,
9,9 % de CPU relevé à l'audit. Aucun outil du dépôt ne s'y connecte.

| Option | Effet | Risque |
|---|---|---|
| **A. Retirer** (recommandé) | −3 nœuds, −9,9 % CPU, −1 unité ; O11 tenu sans discussion | perte de Foxglove/rosbridge pour un usage ponctuel ; remise en route = `ros2 launch rosbridge_server` à la main |
| B. Lier à `127.0.0.1` | garde l'outil, ferme le réseau | 3 nœuds et 9,9 % CPU conservés ; O11 dépend de la définition |
| C. Statu quo | rien à faire | unité exposée sur le réseau sans usage constaté |

## 9. Q12 — documentation (8080)

`clawbot-docs` tourne déjà sur `127.0.0.1:8080`, mais en `mkdocs serve` (mode
développement : reconstruction à chaque requête, watcher de fichiers).

| Option | Effet | Risque |
|---|---|---|
| **A. `mkdocs build` + serveur statique sur `127.0.0.1`** (recommandé) | pas de watcher, empreinte minimale, même URL | le site n'est plus régénéré à chaud ; reconstruire après édition (`mkdocs build`) |
| B. Statu quo (`mkdocs serve`) | rien à faire | processus de développement en production |
| C. Retirer le service | −1 unité | documentation consultable seulement en local par `mkdocs build` manuel |

## 10. Ce qui est demandé avant toute action

1. **Valider cet inventaire** (unités → lancement, liste `attic/`, suppressions).
2. **Q11** : A (retirer), B (lier à 127.0.0.1) ou C (statu quo).
3. **Q12** : A (build statique local), B (statu quo) ou C (retirer).
4. **Définition de O11** : 15 hors infrastructure et hors rosbridge, ou un autre compte.
5. Confirmer la suppression de `bridge_mcp` et de `ros2_llm_bridge` (python), qui ne sont
   plus déployés mais dont `clawbot-health` (oneshot Telegram) dépend encore.

Rien n'est déplacé, supprimé ni déployé tant que ces cinq points ne sont pas tranchés.
