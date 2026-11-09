---
title: "llm2ros bridge — architecture du système (diagrammes)"
date: "2026-11-10T06:38:00+08:00"
author: "Hermes Agent"
tags: [software, llm, ros2, architecture, diagrammes, mermaid, c4]
status: validé
---

# llm2ros bridge — architecture

Document d'architecture du pont LLM → ROS 2 du Clawbot X3 : contexte, conteneurs, composants, séquences, états, déploiement et modèle de concurrence. Les diagrammes sont écrits en Mermaid (rendu par Obsidian, GitHub, VS Code) ; une vue ASCII les précède pour les lecteurs en terminal.

État constaté : [[llm2ros_bridge]]. Exigences : [[llm2ros_bridge_specification]]. Défauts et architecture cible : [[llm2ros_bridge_coherence_et_approche]].

## 1. Vue ASCII de synthèse

```
   Agent LLM / opérateur                 navigateur Foxglove / dashboard
            |                                        |
            | HTTP 8000 (aucune auth)                | ws 9090
            v                                        v
   +-------------------------+              +------------------+
   |  api_server  (C++)      |              |  rosbridge       |
   |  nœud llm_bridge_node   |              |  websocket       |
   |  18 outils, 4 modes     |              +------------------+
   +------------+------------+
                | HTTP local 8001 (libcurl, 10 s de délai)
                v
   +-------------------------+        +--------------------------+
   |  hardware_service       |  ROS2  |  driver_node             |
   |  (Python, FastAPI)      |------->|  Mcnamu_driver_X3        |
   |  nœud HardwareNode      |        |  /dev/myserial @115200   |
   |  watchdog 300 ms        |        +------------+-------------+
   |  23 routes REST         |                     |
   +------------+------------+                     v
                |                          carte Rosmaster (MCU)
                |                          roues, servos, pince
                v
   /cmd_vel  /servo_ctrl  /RGBLight  /Buzzer      (domaine ROS 2 = 28)
```

## 2. Contexte (C4 niveau 1)

```mermaid
flowchart LR
    LLM["Agent LLM distant<br/>client d'outils"]
    OPS["Opérateur humain<br/>ou supervision"]
    DASH["Tableau de bord web<br/>Foxglove / rosbridge"]
    BRIDGE["llm2ros bridge<br/>pont LLM vers ROS 2"]
    ROBOT["Clawbot X3<br/>roues, bras, pince, capteurs"]
    YOLO["Service de détection YOLO<br/>port 8003"]

    LLM -->|"HTTP : appels d'outils"| BRIDGE
    OPS -->|"HTTP : arrêt, mode"| BRIDGE
    DASH -->|"WebSocket 9090 : topics"| ROBOT
    BRIDGE -->|"HTTP : détection"| YOLO
    BRIDGE -->|"ROS 2 : commandes et mesures"| ROBOT
```

## 3. Conteneurs (C4 niveau 2)

Deux processus exécutent le pont ; ils partagent le domaine DDS 28 et sont lancés par systemd.

```mermaid
flowchart TB
    subgraph CLIENTS["Zone clients"]
        LLM["Agent LLM"]
        OPS["Opérateur"]
    end

    subgraph HOST["Jetson Orin NX, hôte yahboom"]
        subgraph DOMAIN["Domaine ROS 2 n° 28"]
            subgraph A["Conteneur A : api_server (C++ , port 8000)"]
                ROUTER["Routeur HTTP<br/>thread par connexion"]
                TOOLS["Registre de 18 outils<br/>validation des arguments"]
                MODES["Gestionnaire de modes<br/>4 modes"]
                DISPATCH["Répartiteur d'actions<br/>identifiant de corrélation"]
                NODEA["Nœud llm_bridge_node<br/>publication /cmd_vel en repli"]
            end
            subgraph B["Conteneur B : hardware_service (Python, port 8001)"]
                FASTAPI["FastAPI / uvicorn<br/>23 routes"]
                NODEB["Nœud HardwareNode<br/>publications et abonnements"]
                WD["Watchdog<br/>période 300 ms"]
            end
            DRV["driver_node<br/>Mcnamu_driver_X3"]
            CAMNODE["camera/camera<br/>Astra Pro+"]
            ROSBR["rosbridge_websocket<br/>port 9090"]
        end
        subgraph EXT["Services annexes"]
            YOLOSVC["YOLO inference<br/>port 8003"]
        end
        subgraph HW["Matériel"]
            MCU["Carte Rosmaster<br/>via /dev/myserial"]
            UVC["Caméras UVC<br/>/dev/video0 et video1"]
        end
    end

    LLM -->|"HTTP 8000"| ROUTER
    OPS -->|"HTTP 8000"| ROUTER
    ROUTER --> TOOLS --> MODES --> DISPATCH
    DISPATCH -->|"HTTP 8001"| FASTAPI
    DISPATCH -->|"publication directe"| NODEA
    DISPATCH -->|"HTTP 8003"| YOLOSVC
    FASTAPI --> NODEB
    NODEB -->|"/cmd_vel /servo_ctrl /RGBLight /Buzzer"| DRV
    NODEB -->|"/capture via OpenCV"| UVC
    DRV --> MCU
    WD --> NODEB
    CAMNODE -->|"/camera/* /tf"| ROSBR
```

| Lien | Protocole | Adresse | Authentification | Délai |
|---|---|---|---|---|
| Client → A | HTTP/1.1 | `0.0.0.0:8000` | Aucune (`API_KEY` non défini) | 10 s de réception |
| A → B | HTTP/1.1 via libcurl | `localhost:8001` | Aucune | 10 s (`HARDWARE_SERVICE_TIMEOUT`) |
| A → YOLO | HTTP/1.1 via libcurl | `localhost:8003` | Aucune | 15 s |
| A → ROS 2 | DDS | domaine 28 | — | — |
| B → ROS 2 | DDS | domaine 28 | — | — |
| Tableau de bord → robot | WebSocket | `0.0.0.0:9090` | Aucune | — |

## 4. Composants du conteneur A (C4 niveau 3)

```mermaid
flowchart TB
    subgraph APISERVER["api_server.cpp — main et serveur"]
        MAIN["main<br/>init rclcpp, threads, signal"]
        SRV["ApiServer<br/>socket, accept, thread par client"]
        BUILD["build_response<br/>CORS, Content-Length"]
    end
    subgraph APP["Couche applicative"]
        HANDLER["lambda de routage<br/>health, tools, durations, mode, command, evolution"]
        AUTH["Contrôle de jeton<br/>actif seulement si API_KEY défini"]
        ASYNC["std::async + wait_for<br/>délai par outil"]
    end
    subgraph CORE["Cœur métier"]
        REG["ToolRegistry<br/>18 ToolDef, schémas, validate_args"]
        MM["ModeManager<br/>4 modes, transitions"]
        AH["ActionHandler<br/>dispatch, cid"]
        BN["BridgeNode<br/>exécuteurs par outil"]
        HC["HttpClient<br/>libcurl"]
        NODE["Nœud ROS 2 llm_bridge_node"]
    end

    MAIN --> SRV --> HANDLER
    HANDLER --> AUTH
    HANDLER --> REG
    HANDLER --> MM
    HANDLER --> ASYNC --> AH --> BN
    BN --> HC
    BN --> NODE
    SRV --> BUILD
```

| Composant | Fichier | Responsabilité | Dépendances |
|---|---|---|---|
| `ApiServer` | `src/api_server.cpp:140-295` | Socket TCP, analyse de la requête, réponse HTTP | POSIX sockets |
| Routage | `src/api_server.cpp:329-564` | Huit routes, authentification optionnelle, mode | `ApiServer`, `ToolRegistry`, `ModeManager` |
| `ToolRegistry` | `src/tool_schemas.cpp` | Description des 18 outils, génération des schémas, validation des arguments | `nlohmann::json` |
| `ModeManager` | `src/mode_manager.cpp` | Ensemble d'outils autorisés par mode, transitions | — |
| `ActionHandler` | `src/action_handler.cpp` | Validation, génération du `cid`, répartition vers `BridgeNode` | `ToolRegistry`, `BridgeNode` |
| `BridgeNode` | `src/bridge_node.cpp` | Traduction outil → HTTP 8001 ou commande système ; repli `/cmd_vel` | `HttpClient`, ROS 2 |
| `HttpClient` | `src/http_client.cpp` | GET/POST libcurl, levée d'exception sur code ≥ 400 | libcurl |

## 5. Composants du conteneur B (C4 niveau 3)

```mermaid
flowchart LR
    subgraph B["hardware_service.py"]
        START["startup<br/>rclpy.init, threads"]
        API2["23 routes FastAPI<br/>Pydantic ge/le"]
        NODE2["HardwareNode<br/>état capteurs en mémoire"]
        WDG["watchdog<br/>publie Twist nul"]
        SUBS["Abonnements<br/>voltage, imu, vel_raw, map, detections"]
        PUBS["Publications<br/>cmd_vel, servo_ctrl, Buzzer, RGBLight"]
        PROC["Gestion de processus<br/>slam_launch.py, systemctl"]
    end
    START --> API2
    START --> NODE2
    START --> WDG
    SUBS --> NODE2
    API2 --> PUBS
    API2 --> PROC
    WDG --> PUBS
    PUBS --> NODE2
```

| Ressource partagée | Producteur | Consommateur | Mécanisme |
|---|---|---|---|
| Tension | `/voltage` (10 Hz) via `driver_node` | `/battery`, `/telemetry` | Attribut `battery_volt` |
| IMU | `/imu/data_raw` (10 Hz) | `/telemetry` | Attributs + horodatage |
| Vitesse mesurée | `/vel_raw` | `/telemetry` | Attributs + horodatage |
| Carte | `/map` (transient local) | `/map/live`, `/maps/save` | Dernier message conservé |
| Détections | `/detections`, `/camera/detection_image` | `/yolo/frame`, `/yolo/status` | Attributs + horodatage |
| Angles de servos | Commandes émises par l'API | `/telemetry` | Dernière consigne (pas de retour capteur) |

## 6. Séquence — appel nominal de lecture

```mermaid
sequenceDiagram
    autonumber
    participant L as Agent LLM
    participant A as api_server 8000
    participant R as ToolRegistry
    participant M as ModeManager
    participant H as ActionHandler
    participant B as BridgeNode
    participant S as hardware_service 8001
    participant N as HardwareNode
    participant D as driver_node

    L->>A: POST /command GetBatteryVoltage
    A->>R: validate_args
    R-->>A: valide
    A->>M: is_tool_available
    M-->>A: autorisé en standby
    A->>H: execute_tool via std::async
    H->>H: génération du cid
    H->>B: execute_get_battery_voltage
    B->>S: GET /battery via libcurl
    S->>N: lecture de battery_volt
    N-->>S: 11.9 V
    S-->>B: JSON voltage et percentage
    B-->>H: chaîne JSON
    H-->>A: chaîne JSON
    A-->>L: 200 result égale chaîne JSON encodée
    Note over D,N: la valeur provient de /voltage publié à 10 Hz par le pilote série
```

Mesure associée : 39 à 51 ms pour l'aller-retour complet (10 appels, 2026-11-10 06:23).

## 7. Séquence — déplacement borné, auto-arrêt et watchdog

```mermaid
sequenceDiagram
    autonumber
    participant L as Agent LLM
    participant B as BridgeNode
    participant S as hardware_service
    participant W as Watchdog 300 ms
    participant R as ROS 2 /cmd_vel
    participant D as driver_node

    L->>B: SetVelocity vx=0.06 duration=1.0
    B->>S: POST /motion
    S->>S: contrôle des bornes Pydantic
    S->>R: publication Twist vx=0.06
    S-->>B: 200 ok
    B->>B: création d'un thread détaché de 1.0 s
    B-->>L: 200 résultat
    loop toutes les 300 ms
        W->>W: écoulé depuis le dernier mouvement
    end
    Note over W: à 1.5 s sans nouvelle commande le watchdog publie zéro
    W->>R: publication Twist nul
    B->>S: POST /motion/stop à t plus 1.0 s
    S->>R: publication Twist nul
    R->>D: /cmd_vel
    D-->>R: /vel_raw 0.000 m/s
```

Points d'architecture : l'auto-arrêt du pont et le watchdog du service sont **deux mécanismes indépendants**, et le thread d'auto-arrêt n'est ni suivi ni annulable (voir ROB-01, ROB-03 dans [[llm2ros_bridge_coherence_et_approche]]).

## 8. Séquence — défaillance du service matériel

```mermaid
sequenceDiagram
    autonumber
    participant L as Agent LLM
    participant B as BridgeNode
    participant S as hardware_service
    participant HC as HttpClient
    participant R as ROS 2 /cmd_vel

    L->>B: Stop
    B->>S: POST /motion/stop
    S--xB: service indisponible ou délai dépassé
    HC-->>B: exception runtime
    B->>R: publication directe d'un Twist nul
    B-->>L: 200 Stop sent to /cmd_vel (hardware service unreachable)
    Note over B,L: l'échec est signalé dans une chaîne de succès HTTP 200
```

## 9. États — modes d'exploitation (implémentation actuelle)

```mermaid
stateDiagram-v2
    [*] --> standby
    standby --> navigation: POST /mode navigation
    standby --> manipulation: POST /mode manipulation
    standby --> evolution: POST /mode evolution
    navigation --> standby: arrêt et pose 1 et LED verte
    manipulation --> standby: arrêt et LED verte
    evolution --> standby: arrêt et pose 1 et LED bleue
    navigation --> manipulation: arrêt puis LED orange
    manipulation --> navigation: arrêt puis LED jaune
    navigation --> evolution: arrêt puis LED bleue
    manipulation --> evolution: arrêt puis LED bleue
    evolution --> navigation: arrêt puis LED jaune
    evolution --> manipulation: arrêt puis LED orange

    note right of standby
        état initial à chaque démarrage
        aucune persistance
        transitions exécutées dans le thread HTTP
    end note
```

Les routes `/evolution/build` et `/evolution/test` restent accessibles quel que soit l'état : elles ne figurent pas dans le diagramme de modes.

## 10. Déploiement

```mermaid
flowchart TB
    subgraph UNIT["Unités systemd"]
        U1["ros2-hardware-service.service<br/>python3 hardware_service.py<br/>port 8001"]
        U2["ros2-driver-node.service<br/>Mcnamu_driver_X3<br/>Requires et After U1"]
        U3["ros2-llm-bridge-cpp.service<br/>api_server<br/>Requires et After U1<br/>ports 8000 et 8001 via env"]
        U4["orbbec-camera.service<br/>profil FastDDS"]
        U5["rosbridge.service<br/>port 9090"]
        U6["yolo-inference.service<br/>port 8003"]
        U7["clawbot-joy-teleop.service"]
        U8["yahboom_oled.service"]
    end
    subgraph ENV["Variables communes"]
        E1["ROS_DOMAIN_ID=28"]
        E2["HARDWARE_SERVICE_URL=http://localhost:8001"]
        E3["YOLO_SERVICE_URL=http://localhost:8003"]
        E4["MAX_LINEAR_MS=0.06"]
        E5["MOTION_WATCHDOG_S=1.5"]
        E6["LIDAR_SAFETY_REQUIRED=false"]
    end
    U1 --> E1
    U3 --> E2
    U3 --> E3
    U2 --> U1
    U3 --> U1
```

| Unité | Redémarrage | Dépendance déclarée | Utilisateur |
|---|---|---|---|
| `ros2-hardware-service.service` | — | aucune | `jetson` |
| `ros2-driver-node.service` | `Restart=on-failure`, 5 s | `Requires=ros2-hardware-service` | `jetson` |
| `ros2-llm-bridge-cpp.service` | `Restart=on-failure`, 3 s | `Requires=ros2-hardware-service` | `jetson` |

## 11. Modèle de concurrence

| Processus | Threads observés | Risque structurel |
|---|---|---|
| `api_server` | thread principal (accept non bloquant, pause 50 ms), thread `rclcpp::spin`, 1 thread détaché par connexion, 1 thread détaché par `SetVelocity` | Connexions et threads non bornés ; aucun verrou sur les actionneurs |
| `hardware_service` | boucle asyncio uvicorn, thread de spin ROS (démon), thread watchdog (démon, 300 ms) | État capteurs lu sans verrou depuis la boucle asyncio |
| `driver_node` | thread rclpy, thread de réception série de `Rosmaster_Lib` | Propriétaire exclusif de `/dev/myserial` |

## 12. Points d'intégration et couplage

| Interface | Type de couplage | Force | Remarque |
|---|---|---|---|
| A → B | HTTP synchrone | Fort | Toute indisponibilité de B dégrade A ; 12 routes de B non exposées |
| A → ROS 2 | DDS, publication `/cmd_vel` | Faible volume | Utilisé uniquement en repli d'échec |
| B → ROS 2 | DDS, 4 publications, 6 abonnements | Fort | Le service dépend de `driver_node` pour toute mesure |
| A → YOLO | HTTP synchrone | Moyen | Indisponibilité détectée à l'appel |
| Clients → A | HTTP sans authentification | Fort et non maîtrisé | Voir SEC-03 et SEC-04 |

## 13. Limites de cette description

Les diagrammes décrivent le comportement constaté et le code source au 2026-11-10 ; ils ne constituent pas une architecture cible. Les écarts, défauts et la cible sont traités dans [[llm2ros_bridge_coherence_et_approche]], et les exigences vérifiables dans [[llm2ros_bridge_specification]].

## 14. Voir aussi

- État constaté et mesures : [[llm2ros_bridge]]
- Analyse de cohérence et architecture cible : [[llm2ros_bridge_coherence_et_approche]]
- Exigences et recette : [[llm2ros_bridge_specification]]
- Défauts du graphe ROS 2 sous-jacent : [[ros2_graph_clawbot]], [[ros2_nav_stack]]
- Matériel piloté : [[rosmaster_x3_mcu]], [[orbbec_astra_pro_plus]], [[batterie_principale]]
- Services supervisés : [[systemd_robot_services]]
