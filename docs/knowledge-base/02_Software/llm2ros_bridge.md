---
title: "llm2ros bridge — état constaté du service LLM → ROS 2"
date: "2026-11-10T06:22:20+08:00"
author: "Hermes Agent"
tags: [software, llm, ros2, api, bridge, architecture, constat]
status: validé
---

# llm2ros bridge — état constaté

Description factuelle du pont entre un modèle de langage et les actionneurs du Clawbot X3, telle que constatée le 2026-11-10 entre 06:18 et 06:25 CST. Retour à l'[[index]]. Spécification cible : [[llm2ros_bridge_specification]]. Analyse de cohérence : [[llm2ros_bridge_coherence_et_approche]].

## 1. Identification du service

| Élément | Valeur | Source |
|---|---|---|
| Nom d'usage | llm2ros bridge | Nommage utilisateur |
| Composant A (passerelle d'outils) | `ros2_llm_bridge_cpp` 2.0.0, exécutable `api_server` | `package.xml`, processus PID 1403 |
| Composant B (service matériel) | `hardware_service.py` (FastAPI 2.0.0) | processus PID 1388 |
| Unités systemd | `ros2-llm-bridge-cpp.service`, `ros2-hardware-service.service` | `systemctl cat` |
| Ports | 8000 (A), 8001 (B) | `ss -ltnp` |
| Domaine ROS 2 | 28 | `Environment=ROS_DOMAIN_ID=28` |
| Utilisateur d'exécution | `jetson` (uid 1000) | `systemctl cat` |
| Versionnement du composant A | Non versionné : `git status` retourne `?? ros2_llm_bridge_cpp/` | `git status --porcelain` |
| Dépendances du composant A | `rclcpp`, `geometry_msgs`, `std_msgs`, `sensor_msgs`, `nav_msgs`, `nlohmann_json`, `libcurl` | `CMakeLists.txt` |
| Tests du composant A | Aucun test C++ (`BUILD_TESTING` absent de `CMakeLists.txt`) | `grep -n BUILD_TESTING CMakeLists.txt` |

## 2. Architecture d'exécution

```
Client LLM (Claude / agent)
        │  POST /command  {"function": ..., "arguments": {...}}
        ▼
┌───────────────────────────────────────────┐
│ api_server (C++, port 8000)               │
│  BridgeNode : nœud ROS 2 llm_bridge_node  │
│  ToolRegistry (18 outils + validation)    │
│  ModeManager (4 modes)                    │
│  ActionHandler (dispatch + correlation)   │
└───────────────────────────────────────────┘
        │  HTTP GET/POST (libcurl)
        ▼
┌───────────────────────────────────────────┐
│ hardware_service.py (FastAPI, port 8001)  │
│  nœud ROS 2 HardwareNode + watchdog       │
└───────────────────────────────────────────┘
        │  publications ROS 2 (domaine 28)
        ▼
/cmd_vel · /servo_ctrl · /RGBLight · /Buzzer
        │
        ▼
driver_node (Mcnamu_driver_X3) → /dev/myserial → carte Rosmaster
```

Le pont ne dialogue avec le matériel que par deux voies : HTTP vers le service 8001, et publication directe sur `/cmd_vel` en repli lors d'un échec du service ([[rosmaster_x3_mcu]], [[yahboomcar_bringup_driver_node]]).

## 3. Surface HTTP exposée

### 3.1 Composant A — port 8000

| Route | Méthode | Rôle | Preuve |
|---|---|---|---|
| `/health` | GET | Vivacité, renvoie `{"status":"healthy"}` | `curl → 200` |
| `/tools` | GET | Schémas d'outils, `format=openai\|anthropic\|raw` | `curl → 200, 6 899 o` |
| `/durations` | GET | Durées maximales et `auto_stop` par outil | `curl → 200, 18 entrées` |
| `/mode` | GET | Mode courant et outils autorisés | `curl → 200` |
| `/mode` | POST | Changement de mode | Code |
| `/command` | POST | Exécution d'un outil | `curl → 200` |
| `/evolution/build` | POST | `colcon build` d'un paquet arbitraire | Code `api_server.cpp:381-394` |
| `/evolution/test` | POST | Exécution d'une suite de tests | Code `api_server.cpp:397-418` |

`/openapi.json` retourne 404 sur 8000 : aucune spécification machine-readable n'est publiée.

### 3.2 Composant B — port 8001

Vingt-trois routes FastAPI, dont la spécification OpenAPI est servie (`/openapi.json → 200, 15 670 o`) :

`/motion`, `/motion/stop`, `/servo`, `/arm`, `/claw`, `/arm/pose/{id}`, `/beep`, `/lamps`, `/battery`, `/telemetry`, `/capture`, `/yolo/frame`, `/yolo/status`, `/system/status`, `/slam/start`, `/slam/stop`, `/slam/status`, `/map/live`, `/maps`, `/maps/save`, `/maps/{name}/image`, `/maps/{name}` (DELETE), `/health`.

Douze de ces routes ne sont pas atteignables depuis le pont : `telemetry`, `system/status`, `slam/*` (3), `map/live`, `maps` (4), `yolo/frame`, `yolo/status`.

## 4. Contrat d'outils

18 outils publiés par `/tools` (le commentaire d'en-tête de `tool_schemas.cpp:2` et le `README.md:6` annoncent 17).

| Outil | Catégorie | `timeout_sec` | `max_duration_sec` | `auto_stop` | Modes autorisés |
|---|---|---|---|---|---|
| `SetVelocity` | mouvement | 15 | 10 | oui | standby, navigation |
| `Stop` | mouvement | 2 | — | non | tous |
| `NavigateTo` | mouvement | 60 | 30 | oui | navigation |
| `Speak` | audio | 15 | 10 | non | standby, navigation, manipulation |
| `Listen` | audio | 10 | 5 | non | standby, navigation, manipulation |
| `CaptureCamera` | perception | 10 | 3 | non | navigation, manipulation, evolution |
| `AnalyzeScene` | perception | 15 | — | non | navigation, manipulation |
| `RecognizeFace` | perception | 10 | — | non | manipulation |
| `RecognizeObject` | perception | 10 | — | non | navigation, manipulation |
| `RecognizeQRCode` | perception | 10 | — | non | navigation, manipulation |
| `DetectObjects` | perception | 15 | 1 | non | navigation, manipulation |
| `ControlServo` | bras | 5 | 3 | non | manipulation |
| `ControlArm` | bras | 10 | 5 | non | manipulation |
| `ControlClaw` | bras | 5 | 2 | non | manipulation |
| `SetArmPose` | bras | 10 | 5 | non | standby, navigation, manipulation |
| `Beep` | périphérique | 5 | 5 | non | tous |
| `SetLamps` | périphérique | 2 | — | non | tous |
| `GetBatteryVoltage` | périphérique | 3 | — | non | tous |

Source : `GET /durations`, `GET /mode`, `src/tool_schemas.cpp`, `src/mode_manager.cpp:15-45`.

## 5. Chaîne d'exécution d'une requête

```
POST /command {"function":"GetBatteryVoltage","arguments":{}}
  → ToolRegistry::validate_args          (type, bornes, enum, cardinalité)
  → ModeManager::is_tool_available        (403 si mode incompatible)
  → std::async + wait_for(timeout_sec)    (api_server.cpp:538-546)
  → ActionHandler::execute_tool           (validation + cid)
  → BridgeNode::execute_*                 (libcurl → 8001, ou std::system)
  → hardware_service (Pydantic ge/le) → publication ROS 2
  ← {"result":"<chaîne JSON encodée>"}    (api_server.cpp:549)
```

| Caractéristique mesurée | Valeur | Méthode |
|---|---|---|
| Latence `GetBatteryVoltage` (n = 10) | min 39,0 ms · médiane 50,0 ms · max 51,0 ms | 10 appels séquentiels, 06:23:41 CST |
| Latence `Stop` | 51,6 ms | 1 appel |
| Taille de réponse `/battery` via le pont | 64 o (double encodage JSON) | Mesure |
| Taille de réponse `/capture?camera=front&save=false` (appel direct 8001) | 47 834 o (base64 : 47 764 caractères, JPEG ≈ 35,8 Ko, 640 × 480) | `curl`, 06:24:10 CST |

## 6. Limites de vitesse : trois valeurs distinctes

| Emplacement | Valeur linéaire | Valeur angulaire | Source |
|---|---|---|---|
| Schéma d'outil et validation du pont | ±0,06 m/s | ±0,25 rad/s | `tool_schemas.cpp:25-37` |
| Navigation par estime | 0,05 m/s | 0,20 rad/s | `bridge_node.cpp:135-136` |
| Service matériel (défaut du code) | 0,5 m/s | 1,5 rad/s | `hardware_service.py:50-51` |
| Service matériel (environnement systemd) | 0,06 m/s | 0,25 rad/s | `MAX_LINEAR_MS=0.06`, `MAX_ANGULAR_RS=0.25` |

Le service matériel rejette hors bornes avec HTTP 422 (validation Pydantic `ge`/`le`, `hardware_service.py:289-292`). Le champ `clamped` testé par `bridge_node.cpp:66` n'existe pas dans la réponse de `/motion` : le message « speed was clamped » est inatteignable.

## 7. Modes

| Mode | ID | Outils | Transition (effets exécutés) |
|---|---|---|---|
| `standby` | 0 | 8 | arrêt, pose bras 1, LED verte |
| `navigation` | 1 | 14 | arrêt, pose bras 1, LED jaune |
| `manipulation` | 2 | 16 | arrêt, LED orange |
| `evolution` | 3 | 5 | arrêt, pose bras 1, LED bleue |

Source : `src/mode_manager.cpp:13-46`, `src/api_server.cpp:445-473`. Le mode est conservé en mémoire du processus, sans persistance : tout redémarrage revient à `standby`. Les routes `/evolution/build` et `/evolution/test` ne consultent pas le mode courant.

## 8. Sécurité observée

| Constat | Valeur | Preuve |
|---|---|---|
| Authentification | Désactivée : `API_KEY` absent des unités systemd | `grep API_KEY /etc/systemd/system/ros2-*.service` → aucune |
| Écoute réseau | `0.0.0.0:8000` et `0.0.0.0:8001` | `ss -ltnp` |
| Accessibilité LAN | `http://192.168.1.47:8000/health` → 200 ; idem 8001 | `curl` |
| CORS | `Access-Control-Allow-Origin: *` | `api_server.cpp:72` |
| Exécution de commandes système | `std::system` avec concaténation de chaînes | `bridge_node.cpp:106`, `api_server.cpp:385-388` |
| Exécution de commande arbitraire prouvée | Oui, via l'outil `Speak` | [[ERR-2026-11-10-004_execution_de_commande_non_authentifiee]] |

## 9. Voir aussi

- Spécification cible et exigences : [[llm2ros_bridge_specification]]
- Analyse de cohérence et approche retenue : [[llm2ros_bridge_coherence_et_approche]]
- Trace de sécurité ouverte : [[ERR-2026-11-10-004_execution_de_commande_non_authentifiee]]
- Graphe ROS 2 et nœuds : [[ros2_graph_clawbot]]
- Lien série et carte de commande : [[rosmaster_x3_mcu]]
- Capteur RGB-D exploité par la capture : [[orbbec_astra_pro_plus]]
