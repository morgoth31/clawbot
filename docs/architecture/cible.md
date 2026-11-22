# Architecture cible Clawbot X3 — référentiel normatif

> Destinataire : l'agent Hermes (profil développeur) et tout humain qui modifie le robot.
> Ce fichier fait foi pour les noms, types, codes et règles. Les prompts `P00` à `P16` y renvoient par numéro de section (`§3.2`).
> Le raisonnement qui justifie ces choix est dans le document « Clawbot X3 — Analyse et architecture cible pour l'agent Hermes ».
> Les identifiants `Sxx`, `Rxx`, `Oxx`, `Qxx`, `Cxx` renvoient au dossier d'audit du 2026-11-22 (`docs/audit/2026-11-22/`).

Version : 1.0 — 2026-11-22. Toute modification de ce fichier passe par le cycle de `clawbot-dev-cycle` avec une exigence `REQ-ARCH-xxx`.

---

## 1. Invariants (non négociables)

| ID | Invariant | Vérifié par |
|---|---|---|
| INV-01 | Seul `safety_arbitrator` publie `/cmd_vel_safe`. | test d'intégration : `ros2 topic info /cmd_vel_safe` → 1 éditeur |
| INV-02 | Seul `driver_node` ouvre le port série du MCU (C08). | `lsof` / `fuser` sur le device : 1 PID |
| INV-03 | `driver_node` met les moteurs à zéro si aucune consigne n'est reçue depuis `cmd_timeout_s` (défaut 0,3 s). | test sur cales, P03 |
| INV-04 | Aucun outil MCP ne publie de vitesse, d'angle de servo, ni ne modifie un réglage de sécurité. Aucun outil MCP ne réarme l'arrêt d'urgence. | revue de `clawbot_mcp`, test de liste d'outils |
| INV-05 | L'arrêt d'urgence (`/safety/estop`) est verrouillé : seule une action humaine (service `/safety/reset_estop` appelé depuis le tableau de bord opérateur) le lève. | test P04 |
| INV-06 | Aucun test automatique ne s'exécute dans le domaine 28. Unitaires : `ROS_DOMAIN_ID=98`. Intégration : `ROS_DOMAIN_ID=99`. | `scripts/check.sh` refuse de tourner si `ROS_DOMAIN_ID=28` |
| INV-07 | Les budgets de reprise (§6.3) sont comptés par l'exécutif, jamais par le LLM. | test P09 |
| INV-08 | Toute action de contrôle de processus passe par systemd (D-Bus) sur une liste blanche. Jamais de `pkill`, `kill -9` ou recherche de processus par motif. | grep CI : `pkill`, `pgrep -f` interdits dans le code |
| INV-09 | Chaque flux capteur attendu est déclaré dans le manifeste de santé (§8) ; un flux absent produit `SENSOR_STALE` en moins de 3 s. | test P05 |
| INV-10 | Une source unique par composant : pas de copie de fichier source entre deux paquets. | `scripts/check.sh` (détection de doublons par sha256) |

---

## 2. Couches et paquets

| Couche | Nœud / processus | Paquet | Statut |
|---|---|---|---|
| L5 Hermes | profil `clawbot-pilot`, profil `clawbot-dev` | hors dépôt | nouveau |
| L4 Passerelle | `clawbot_mcp_server` | `clawbot_mcp` (remplace `bridge_mcp`) | refonte |
| L4 Passerelle | `api_server` (HTTP 8000) | `ros2_llm_bridge_cpp` | conservé, rebranché sur L3 |
| L3 Exécutif | `mission_executive` | `clawbot_executive` | nouveau |
| L3 Exécutif | `skill_server` | `clawbot_executive` | nouveau |
| L3 Exécutif | `capability_manager` | `clawbot_capabilities` | nouveau |
| L3 Exécutif | `health_monitor` | `clawbot_health` | nouveau |
| L3 Exécutif | — (bibliothèque) | `clawbot_common` : table d'erreurs, schémas JSON, validation, construction des rapports | nouveau (P06) |
| L3 Exécutif | `director` | `clawbot_director` | devient façade de compatibilité de `/director/command` |
| L2 Capacités | EKF, SLAM, Nav2, bras, perception, caméras | vendor + `clawbot_arm_controller`, `clawbot_moveit_config`, `yolo_node` | activés à la demande |
| L1 Sécurité | `safety_arbitrator` | `clawbot_safety` | refonte en multiplexeur |
| L1 Sécurité | `sentinel` | `clawbot_sentinel` | ne publie plus de vitesse, publie `/safety/estop` |
| L0 Matériel | `driver_node` | `clawbot_base_driver` (fork interne unique de `yahboomcar_bringup/Mcnamu_driver_X3`) | refonte légère |

---

## 3. Interfaces ROS 2 nouvelles (paquet `clawbot_interfaces`)

### 3.1 `action/ExecuteSkill.action`

```
# Goal
string mission_id          # vide : le serveur en génère un (UUID4)
string skill               # nom du registre (§7)
string params_json         # validé contre le schéma JSON du skill ; refus = REJECTED + INVALID_PARAMS
float32 timeout_s          # 0 : délai par défaut du skill
---
# Result
uint8 OUTCOME_SUCCEEDED=0
uint8 OUTCOME_FAILED=1
uint8 OUTCOME_CANCELED=2
uint8 OUTCOME_REJECTED=3
uint8 outcome
string error_code          # vide si SUCCEEDED ; sinon un code de §6.1
string error_category      # PRECONDITION | SENSOR | SAFETY | EXECUTION | HARDWARE | INTERFACE | INTERNAL
string message             # phrase courte, en français
string result_json         # sortie utile du skill (ex. chemin d'image, détections)
string failure_report_json # rapport §6.2, vide si SUCCEEDED
---
# Feedback
string phase               # ex. "checking_preconditions", "moving", "settling"
float32 progress           # 0.0 à 1.0
string detail_json
```

### 3.2 `action/ExecuteMission.action`

```
# Goal
string mission_id          # vide : généré
string objective           # objectif en langage naturel, recopié dans le journal
string steps_json          # [{"skill": "...", "params": {...}, "timeout_s": 0}] ; 1 à 20 étapes
uint8 max_escalations      # 0 : défaut 3
float32 max_duration_s     # 0 : défaut 600
---
# Result
uint8 outcome              # mêmes constantes que ExecuteSkill
string mission_id
string state               # état final (§6.4)
string failure_report_json
string summary_json        # étapes réalisées, durées
---
# Feedback
uint16 step_index
uint16 step_count
string state
string current_skill
float32 progress
```

Quand une étape échoue après la relance automatique, l'action se termine avec `outcome=FAILED` et `state=WAITING_DECISION`. La mission reste ouverte : le robot est à l'arrêt, et elle attend une décision (§3.4) pendant `decision_timeout_s` (défaut 120 s), après quoi elle passe en `ABORTED`.

### 3.3 Services

```
# srv/ListCapabilities.srv
---
string capabilities_json   # [{"name","state","units":[...],"requires":[...],"conflicts":[...],"stale_flows":[...]}]

# srv/SetCapability.srv
string name
bool active
float32 timeout_s          # 0 : 30 s
---
bool success
string state               # INACTIVE | STARTING | ACTIVE | DEGRADED | STOPPING | FAILED
string message

# srv/GetMissionReport.srv
string mission_id          # vide : la dernière mission
---
bool found
string report_json         # état, étapes, rapport d'échec, décisions, budget restant

# srv/SubmitDecision.srv
string mission_id
string decision            # RETRY_STEP | RETRY_WITH_PARAMS | SKIP_STEP | REPLACE_REMAINING | ABORT
string params_json         # RETRY_WITH_PARAMS : nouveaux params ; REPLACE_REMAINING : nouvelles étapes
string rationale           # justification du LLM, obligatoire, consignée au journal
---
bool accepted
string message
uint8 escalations_left
```

### 3.4 Messages

```
# msg/RobotHealth.msg   — publié sur /clawbot/health à 1 Hz
builtin_interfaces/Time stamp
uint8 LEVEL_OK=0
uint8 LEVEL_WARN=1
uint8 LEVEL_ERROR=2
uint8 level
string[] active_capabilities
string[] stale_flows        # topics attendus dont l'âge dépasse leur max_age_s
string safety_state         # copie de /safety/state
bool estop_latched
float32 voltage
string detail_json

# msg/MissionEvent.msg  — publié sur /clawbot/mission/events
builtin_interfaces/Time stamp
string mission_id
string event               # STARTED | STEP_STARTED | STEP_SUCCEEDED | STEP_FAILED | RETRY | WAITING_DECISION | DECISION | SUCCEEDED | FAILED | ABORTED | CANCELED
string detail_json
```

### 3.5 Récapitulatif des noms

| Nom | Type | Serveur / éditeur |
|---|---|---|
| `/clawbot/execute_skill` | action `ExecuteSkill` | `skill_server` |
| `/clawbot/execute_mission` | action `ExecuteMission` | `mission_executive` |
| `/clawbot/mission/decide` | srv `SubmitDecision` | `mission_executive` |
| `/clawbot/mission/report` | srv `GetMissionReport` | `mission_executive` |
| `/clawbot/mission/events` | msg `MissionEvent` | `mission_executive` |
| `/clawbot/capabilities/list` | srv `ListCapabilities` | `capability_manager` |
| `/clawbot/capabilities/set` | srv `SetCapability` | `capability_manager` |
| `/clawbot/capabilities/state` | `std_msgs/String` (JSON), TRANSIENT_LOCAL | `capability_manager` |
| `/clawbot/health` | msg `RobotHealth`, 1 Hz | `health_monitor` |
| `/safety/estop` | `std_msgs/Bool`, RELIABLE + TRANSIENT_LOCAL | `sentinel`, `clawbot_mcp_server` (`stop_robot`), tableau de bord |
| `/safety/reset_estop` | `std_srvs/Trigger` | `safety_arbitrator` (appelé par le tableau de bord opérateur seulement) |
| `/cmd_vel/teleop`, `/cmd_vel/nav`, `/cmd_vel/skill` | `geometry_msgs/Twist` | voir §4 |

Interfaces existantes **conservées** : toutes celles du §3 du cahier d'entrée (`04_cahier_entree_refonte_pour_claude.md`). `/director/command` garde son type `DirectorCommand` et devient une façade qui traduit `request_json` vers `ExecuteSkill` / `ExecuteMission` (schéma publié en `clawbot_interfaces/schemas/director_command.schema.json`, P06).

---

## 4. Écriture de la vitesse : multiplexeur à priorités

`safety_arbitrator` reçoit des entrées nommées, choisit la plus prioritaire non expirée, applique ses garde-fous (obstacle, capteur périmé, tension, bras hors enveloppe), puis publie `/cmd_vel_safe` à 20 Hz. L'entrée choisie est publiée dans `/safety/state` (champ `source`).

| Entrée | Écrivains autorisés | Priorité | Expiration |
|---|---|---|---|
| `/safety/estop` = `true` | `sentinel`, outil MCP `stop_robot`, tableau de bord | absolue, verrouillée | réarmement manuel (`/safety/reset_estop`) |
| `/cmd_vel/teleop` | téléopération (manette, tableau de bord 8001) | 100 | 0,5 s |
| `/cmd_vel/nav` | contrôleur Nav2 | 50 | 0,5 s |
| `/cmd_vel/skill` | `skill_server` | 40 | 0,5 s |
| `/cmd_vel` (héritage) | anciens éditeurs ; supprimé en P14 | 10 | 0,5 s |

Configuration (`clawbot_safety/config/arbitrator.yaml`, paramètres ROS en lecture seule au runtime) :

```yaml
safety_arbitrator:
  ros__parameters:
    publish_rate_hz: 20.0
    inputs:
      names: [teleop, nav, skill, legacy]
      teleop: {topic: /cmd_vel/teleop, priority: 100, timeout_s: 0.5}
      nav:    {topic: /cmd_vel/nav,    priority: 50,  timeout_s: 0.5}
      skill:  {topic: /cmd_vel/skill,  priority: 40,  timeout_s: 0.5}
      legacy: {topic: /cmd_vel,        priority: 10,  timeout_s: 0.5}
    stale_s: 2.0          # valeur actuelle de thresholds.py (S46)
    cmd_timeout_s: 0.5    # valeur actuelle de thresholds.py (S46)
```

Règles :
- L'arbitre reste **mono-thread** (`SingleThreadedExecutor`). Sa charge (≈ 50 msg/s) ne justifie pas de parallélisme, et le déterminisme prime.
- Chaque callback mesure sa durée ; le maximum glissant est publié dans `/safety/state` (`max_callback_ms`). Objectif O03 : 0 callback > 20 ms.
- Priorité d'ordonnancement dans l'unité systemd : `Nice=-10`, `CPUAffinity=` sur un cœur peu chargé choisi d'après la mesure P01.

---

## 5. Capacités

### 5.1 Manifeste (`clawbot_capabilities/config/capabilities.yaml`)

```yaml
capabilities:
  base:
    description: "Châssis, odométrie, EKF"
    units: [ros2-driver-node.service, clawbot-ekf.service, clawbot-safety-arbitrator.service]
    always_on: true
    ready_when:
      - {topic: /odom, min_hz: 8.0}
      - {topic: /cmd_vel_safe, min_hz: 18.0}
  lidar:
    units: [clawbot-lidar.service]
    always_on: true
    ready_when: [{topic: /scan, min_hz: 9.0}]
  mapping:
    units: [clawbot-slam.service]
    requires: [base, lidar]
    conflicts: [navigation]
    ready_when: [{topic: /map, max_age_s: 30.0}]
  navigation:
    units: [clawbot-nav2.service]
    requires: [base, lidar]
    conflicts: [mapping]
    ready_when: [{action: /navigate_to_pose}]
  arm:
    units: [clawbot-arm-controller.service, clawbot-move-group.service]
    requires: [base]
    ready_when: [{action: /arm_controller/follow_joint_trajectory}, {topic: /arm/joint_states, min_hz: 8.0}]
  wrist_vision:
    units: [clawbot-wrist-camera.service]
    ready_when: [{topic: /wrist_camera/image_raw, min_hz: 25.0}]
  depth_vision:
    units: [orbbec-camera.service]           # ADR-001 (P11) : unité réelle, active depuis le 2026-11-12
    ready_when: [{topic: /camera/depth/image_raw, min_hz: 10.0}]
  voice:
    units: []                                # décrite, non pilotable : aucune unité sur ce poste
    managed: false
    ready_when: [{topic: /voice/command, min_hz: 0.2}]
  detection:
    units: [clawbot-yolo.service]
    requires: [wrist_vision]
    ready_when: [{topic: /perception/detections, min_hz: 2.0}]
```

Les noms d'action et de topic de `navigation` et `arm` sont à confirmer par Hermes en lisant `clawbot_moveit_config` et `clawbot_arm_controller` (P07, P13) ; le manifeste réel fait foi après correction.

### 5.2 Activation

- `capability_manager` démarre et arrête les unités du manifeste, et seulement elles : soit par D-Bus (`org.freedesktop.systemd1`, `StartUnit` / `StopUnit`, mode `replace`), soit par `subprocess.run(["sudo", "-n", "/usr/bin/systemctl", verbe, unité])` en liste d'arguments, jamais par un shell.
- Autorisation, selon la version de polkit (`pkaction --version`) :
  - polkit ≥ 0.106 : règle JavaScript `deploy/polkit/50-clawbot-capabilities.rules` limitée à l'utilisateur `jetson`, aux unités du manifeste et aux verbes `start`/`stop` ;
  - polkit 0.105 (cas d'Ubuntu 22.04, donc probable sur ce Jetson) : les fichiers `.pkla` ne savent pas filtrer par unité ; utiliser `deploy/sudoers/clawbot-capabilities` (une ligne `NOPASSWD` par couple verbe/unité exact, vérifiée par `visudo -cf`), installé dans `/etc/sudoers.d/` avec accord de l'opérateur.
- L'état des capacités est publié à chaque changement sur `/clawbot/capabilities/state` (`std_msgs/String`, JSON, RELIABLE + TRANSIENT_LOCAL).
- Activer une capacité en conflit avec une capacité active est refusé (`CAPABILITY_CONFLICT`) ; les capacités de `requires` inactives sont activées d'abord, dans l'ordre.
- Après `StartUnit`, l'état passe à `ACTIVE` seulement quand toutes les conditions `ready_when` sont vraies ; sinon `FAILED` après `timeout_s`.
- Les capacités `always_on` ne peuvent pas être arrêtées via `/clawbot/capabilities/set`.

---

## 6. Échecs

### 6.1 Codes d'erreur

| Catégorie | Code | Relance automatique par l'exécutif | Décisions autorisées pour le LLM |
|---|---|---|---|
| PRECONDITION | `CAPABILITY_INACTIVE` | non | `RETRY_STEP` après activation, `REPLACE_REMAINING`, `ABORT` |
| PRECONDITION | `CAPABILITY_CONFLICT` | non | `REPLACE_REMAINING` (désactiver l'autre capacité d'abord), `ABORT` |
| PRECONDITION | `ARM_NOT_AT_REST` | non | `REPLACE_REMAINING` (insérer `arm_rest`), `ABORT` |
| PRECONDITION | `MAP_MISSING` | non | `REPLACE_REMAINING`, `ABORT` |
| PRECONDITION | `SKILL_SERVER_UNAVAILABLE` | non | `RETRY_STEP` (serveur revenu), `ABORT` |
| SENSOR | `SENSOR_STALE` | 1 fois après 2 s | `RETRY_STEP`, `REPLACE_REMAINING` (mode dégradé), `ABORT` |
| SENSOR | `DEPTH_UNAVAILABLE` | non | `REPLACE_REMAINING` (sans profondeur), `ABORT` |
| SAFETY | `SAFETY_HOLD` | non | `RETRY_STEP` une fois si la cause est levée, `REPLACE_REMAINING`, `ABORT` |
| SAFETY | `OBSTACLE_TOO_CLOSE` | non | `REPLACE_REMAINING` (autre trajet), `ABORT` |
| SAFETY | `ESTOP_LATCHED` | non | `ABORT` seulement ; prévenir l'opérateur |
| SAFETY | `LOW_VOLTAGE` | non | `ABORT` seulement ; prévenir l'opérateur |
| EXECUTION | `TIMEOUT` | 1 fois | `RETRY_WITH_PARAMS`, `REPLACE_REMAINING`, `ABORT` |
| EXECUTION | `GOAL_UNREACHABLE` | non | `RETRY_WITH_PARAMS`, `REPLACE_REMAINING`, `ABORT` |
| EXECUTION | `PLANNING_FAILED` | 1 fois | `RETRY_WITH_PARAMS`, `REPLACE_REMAINING`, `ABORT` |
| EXECUTION | `GRASP_FAILED` | non | `RETRY_WITH_PARAMS`, `SKIP_STEP`, `ABORT` |
| HARDWARE | `SERIAL_LOST` | non | `ABORT` seulement ; prévenir l'opérateur |
| HARDWARE | `SERVO_NO_FEEDBACK` | non | `ABORT` seulement ; prévenir l'opérateur |
| INTERFACE | `INVALID_PARAMS` | non | `RETRY_WITH_PARAMS`, `ABORT` |
| INTERFACE | `UNKNOWN_SKILL` | non | `REPLACE_REMAINING`, `ABORT` |
| INTERNAL | `UNHANDLED_EXCEPTION` | non | `ABORT` seulement |

La table est codée une seule fois, dans le paquet `ament_python` `clawbot_common` (`clawbot_common/clawbot_common/errors.py`), et exportée en JSON (`share/clawbot_common/errors.json`) pour le serveur MCP et la documentation. Le même paquet porte les schémas JSON et l'aide à la validation (créé en P06).

### 6.2 Rapport d'échec (`failure_report_json`)

```json
{
  "schema": "clawbot.failure_report/1",
  "mission_id": "6f1c…",
  "objective": "Va devant la porte et prends une photo",
  "step_index": 1,
  "skill": "navigate_to",
  "params": {"x": 2.0, "y": 0.5, "yaw": 0.0},
  "error_code": "GOAL_UNREACHABLE",
  "error_category": "EXECUTION",
  "message": "Nav2 n'a pas trouvé de chemin",
  "attempts": 1,
  "auto_retries_done": 0,
  "health": {"level": "OK", "active_capabilities": ["base", "lidar", "navigation"], "stale_flows": [], "safety_state": "OK", "estop_latched": false, "voltage": 11.8},
  "last_events": ["…10 derniers MissionEvent…"],
  "allowed_decisions": ["RETRY_WITH_PARAMS", "REPLACE_REMAINING", "ABORT"],
  "budget": {"escalations_left": 2, "same_step_attempts_left": 1, "time_left_s": 412},
  "stamp": "2026-11-22T14:03:11+01:00"
}
```

### 6.3 Budgets (comptés par `mission_executive`)

- `max_escalations` par mission : 3 par défaut.
- Même skill avec les mêmes paramètres : 2 tentatives au total, relance automatique comprise.
- `max_duration_s` : 600 s par défaut, plafonné à 1 800 s.
- `decision_timeout_s` : 120 s ; au-delà, la mission passe en `ABORTED`.
- Une décision hors de `allowed_decisions` est refusée (`accepted=false`) et ne consomme pas de budget.

### 6.4 États de mission

`PENDING → RUNNING → (WAITING_DECISION ⇄ RUNNING)* → SUCCEEDED | FAILED | ABORTED | CANCELED`

### 6.5 Journal

- Un fichier JSON Lines par mission : `/var/lib/clawbot/missions/<AAAA-MM-JJ>/<mission_id>.jsonl`.
- Chaque `MissionEvent`, chaque décision (avec `rationale`) et chaque rapport y est écrit.
- Rotation : conservation 30 jours, contrôlée par `logrotate` (réparé en P02).

---

## 7. Registre initial des skills (`clawbot_executive/config/skills.yaml`)

| Skill | Paramètres (schéma JSON) | Capacités requises | Délai défaut | Bornes |
|---|---|---|---|---|
| `stop` | `{}` | aucune | 2 s | — |
| `wait` | `{seconds}` | aucune | seconds + 1 | 0 < seconds ≤ 30 |
| `move_relative` | `{dx_m, dy_m, max_speed_mps}` | base, lidar | 30 s | \|dx\|, \|dy\| ≤ 2,0 ; max_speed ≤ 0,2 (à confirmer par l'opérateur) |
| `rotate` | `{angle_rad, max_speed_rps}` | base, lidar | 20 s | \|angle\| ≤ 2π ; max_speed ≤ 0,8 |
| `navigate_to` | `{x, y, yaw, frame}` | navigation | 120 s | frame = `map` |
| `save_map` | `{name}` | mapping | 20 s | name = `[a-z0-9_-]{1,32}` |
| `arm_rest` | `{}` | arm | 20 s | pose de repos C10 `[90,180,0,0,90,149]` ±5° |
| `arm_named_pose` | `{pose}` | arm | 20 s | pose ∈ liste YAML validée par l'opérateur |
| `gripper` | `{command}` | arm | 5 s | command ∈ {open, close} |
| `capture_image` | `{camera}` | wrist_vision ou depth_vision | 5 s | camera ∈ {wrist, astra} |
| `detect_objects` | `{camera, classes}` | detection | 10 s | classes ⊂ classes du modèle |

Chaque skill est une classe Python qui implémente `check_preconditions()`, `execute(goal_handle)`, `cancel()`, et renvoie un résultat conforme à §3.1. Le skill ne publie de vitesse que sur `/cmd_vel/skill`.

---

## 8. Santé (`clawbot_health/config/expected_flows.yaml`)

```yaml
flows:
  - {topic: /scan,                     min_hz: 9.0,  max_age_s: 1.0, capability: lidar,        critical: true}
  - {topic: /odom,                     min_hz: 8.0,  max_age_s: 1.0, capability: base,         critical: true}
  - {topic: /imu/data_raw,             min_hz: 9.0,  max_age_s: 1.0, capability: base,         critical: true}
  - {topic: /voltage,                  min_hz: 9.0,  max_age_s: 2.0, capability: base,         critical: true}
  - {topic: /arm/servo_angles,         min_hz: 9.0,  max_age_s: 2.0, capability: base,         critical: false}
  - {topic: /cmd_vel_safe,             min_hz: 18.0, max_age_s: 0.5, capability: base,         critical: true}
  - {topic: /wrist_camera/image_raw,   min_hz: 25.0, max_age_s: 1.0, capability: wrist_vision, critical: false}
  - {topic: /camera/color/image_raw,   min_hz: 25.0, max_age_s: 1.0, capability: depth_vision, critical: false}
  - {topic: /camera/depth/image_raw,   min_hz: 10.0, max_age_s: 1.0, capability: depth_vision, critical: false}
  - {topic: /perception/detections,    min_hz: 2.0,  max_age_s: 2.0, capability: detection,    critical: false}
```

Un flux n'est surveillé que si sa capacité est `ACTIVE`. Valeurs de cadence tirées de C12 (S08, S09) ; seuils à −10 %.

---

## 9. Serveur MCP (`clawbot_mcp`)

- Nœud rclpy unique, construit sur le SDK MCP Python (`FastMCP`). Transport `stdio` si Hermes tourne sur le Jetson ; sinon HTTP « streamable » lié à une seule interface, avec jeton porteur lu dans une variable d'environnement (jamais dans le dépôt).
- Les outils renvoient toujours du JSON avec un champ `ok` (booléen) et, en cas d'erreur, `error_code` de §6.1.

| Outil | Entrée | Sortie | Appelle |
|---|---|---|---|
| `get_robot_status` | — | santé, capacités, mission en cours, e-stop | `/clawbot/health`, `/clawbot/capabilities/list` |
| `list_capabilities` | — | liste §3.3 | `/clawbot/capabilities/list` |
| `set_capability` | `name`, `active` | état final | `/clawbot/capabilities/set` |
| `list_skills` | — | nom, description, schéma JSON, capacités requises | registre §7 |
| `start_skill` | `skill`, `params`, `timeout_s?` | `mission_id` | `/clawbot/execute_mission` (mission à 1 étape) |
| `start_mission` | `objective`, `steps`, `max_duration_s?` | `mission_id` | `/clawbot/execute_mission` |
| `get_mission_status` | `mission_id` | état, étape, progression | feedback mémorisé |
| `cancel_mission` | `mission_id` | état | annulation du goal |
| `get_failure_report` | `mission_id?` | rapport §6.2 | `/clawbot/mission/report` |
| `submit_decision` | `mission_id`, `decision`, `params?`, `rationale` | accepté, budget restant | `/clawbot/mission/decide` |
| `stop_robot` | `reason` | `ok` | publie `/safety/estop=true` |
| `get_snapshot` | `camera` | chemin ou base64 JPEG réduit (≤ 640 px) | skill `capture_image` |

Outils interdits : publication de `Twist`, d'angles de servo, réarmement d'e-stop, modification de paramètres de sécurité, exécution de commandes shell.

---

## 10. Conventions de développement

- **Arbre :** paquets à la racine (existant). Nouveaux dossiers : `requirements/`, `docs/architecture/`, `docs/audit/2026-11-22/`, `deploy/` (unités, polkit, profils DDS), `scripts/`.
- **Exigences :** `requirements/<domaine>.yaml`, domaines `ARCH`, `SAFETY`, `DRV`, `EXEC`, `CAPA`, `HEALTH`, `MCP`, `PERC`, `ARM`, `OPS`, `TEST`, `PERF`, `NET`. Format dans le skill `clawbot-dev-cycle` (`templates/requirement.yaml`).
- **Tests :** pytest ; marqueur `@pytest.mark.req("REQ-XXX-NNN")` déclaré dans `pytest.ini`. Unitaires dans `<paquet>/test/`, intégration dans `tests/integration/` (launch_testing, domaine 99), matériel dans `tests/hardware/` (jamais lancés automatiquement, procédure écrite).
- **Point d'entrée unique :** `scripts/check.sh` — `lint` (flake8 ou ruff, plafonné par `requirements/.lint_baseline`), `unit`, `cpp`, `trace`, `interdits`, `doublons`, `cliquets` (REQ-ARCH-015), `--integration` (domaine 99) et `--build` (construction depuis zéro sous `env -i`, dans `/tmp`, seul l'underlay `/opt/ros/humble`). `--etape <nom>` exécute une seule étape. Un contrôle absent n'avertit pas : il échoue (REQ-TEST-011).
- **Branches :** `feat/REQ-<ID>-<slug>`, `fix/REQ-…`. Commits : `<type>(<paquet>): <résumé> [REQ-…]`.
- **Déploiement :** procédure du skill `clawbot-deploy` ; journal dans `deploy/journal/AAAA-MM-JJ_<sujet>.md`.
