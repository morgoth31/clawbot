# Plan d'exécution — architecture S1/S2 du Clawbot X3 Plus

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** construire le Système 1 (proprioception, arbitre réflexe, directeur, sentinel) qui sert de
tampon de sécurité et de filtre d'attention au Système 2, en fermant d'abord les verrous qui le
rendent aveugle ou impotent.

**Architecture :** hybride, décrite au §5 du document de conception. Nav2 garde son BT interne ; nos
skills sont des serveurs d'action Python ; un directeur séquence leurs états en JSON ; un arbitre
réflexe à 20 Hz, hors du chemin de planification, possède la sortie actionneurs et le dernier mot.

**Tech stack :** ROS 2 Humble (domaine 28 sur le robot, **99 pour tous les tests**),
`robot_localization`, `twist_mux`, `slam_toolbox`, `nav2_bt_navigator`, MoveIt 2, rclpy + pytest,
`bridge_mcp` (serveur MCP existant, 22 outils).

**Spec :** `docs/superpowers/specs/2026-11-11-architecture-s1-s2-design.md`

## Global Constraints

- Tests **toujours** en `ROS_DOMAIN_ID=99` ; le 28 est interdit pendant un test (pollution du graphe
  réel, ENV-01). Les essais physiques, eux, tournent en 28.
- Ne jamais ouvrir `/dev/myserial` pendant que `ros2-driver-node.service` tourne : le driver est le
  seul propriétaire du port série.
- Le bras ne bouge physiquement qu'avec un opérateur présent, espace dégagé, batterie accessible.
- Tout build se fait hors du venv Hermes : `unset VIRTUAL_ENV PYTHONPATH && export PATH=/usr/bin:/bin`
  puis `source /opt/ros/humble/setup.bash`.
- Clean build exigé après chaque changement de code : `rm -rf build install log`, `colcon build`,
  redémarrage du service concerné, suite de tests, codes de sortie reportés.
- La suite existante (`tests/mcp_bridge`, 113 tests verts) ne doit jamais régresser.
- Documentation et messages en français ; base OKF validée (0 erreur) à chaque commit qui la touche.
- Aucun secret dans le dépôt ni dans la documentation.

## Review Focus

Cinq classes d'entrée que la spec n'énumère pas et qu'un utilisateur rencontrera avant nous. Chacune
a son test dans la tâche qui possède le code.

1. **Valeurs de capteur aberrantes** — un `/imu/data_raw` qui publie `NaN` ou un angle de servo à
   `-5` (cas réel du servo 4) ne doit jamais produire une décision de sécurité : l'arbitre traite
   l'invalidité comme une condition d'arrêt, pas comme une valeur.
2. **Flux muet ou périmé** — `/scan` absent, `/voltage` figé : un garde-fou ne peut pas se taire
   parce que sa source est morte ; la péremption déclenche `SENSOR_STALE`, pas le silence.
3. **Batterie sous charge** — 11,9 V au repos peut tomber à 10,4 V pendant un démarrage moteur : la
   moyenne glissante de 10 s doit éviter un refus de tâche sur un pic transitoire.
4. **Deux demandes rapprochées** — deux appels de skill à 200 ms d'intervalle : le second reçoit
   `BUSY` avec le `task_id` courant, jamais une exécution concurrente silencieuse.
5. **Annulation pendant un mouvement** — `cancel_task` pendant une trajectoire de bras se termine au
   point sûr, en moins de 200 ms, et laisse le bras dans une pose connue.

---

## Lots, dépendances et critères de sortie

| Lot | Contenu | Dépend de | Critère de sortie (mesuré) |
|---|---|---|---|
| **L1** | Odométrie : `/vel_raw` + IMU → EKF → `/odom` + TF `odom→base_link` ; correction ERR-009 | — | 2 m en ligne droite, dérive < 5 % ; consigne 0,1 m/s → vitesse mesurée ±10 % |
| **L2** | Proprioception entrelacée (`/arm/servo_angles`) + arbitre réflexe + propriété unique de `/cmd_vel` | L1 | `/imu` et `/vel_raw` ≥ 9,5 Hz pendant les lectures servo ; arrêt obstacle < 15 cm en < 100 ms, journalisé ; un seul éditeur sur `/cmd_vel` |
| **L3** | Directeur : registre de tâche, `task_id`, préconditions, séquences JSON, `WAITING_CONFIRMATION` | L2 | second skill refusé en `BUSY` ; `cancel_task` < 200 ms ; séquence de 3 étapes exécutée et journalisée |
| **L4** | Sentinel : machine `IDLE/WATCHING/ENGAGED`, VAD, YOLO 1-2 Hz, mots d'arrêt locaux | L3 | réveil S2 accepté < 500 ms ; aucun réveil en double sur 10 min ; « stop » traité sans S2 |
| **L5** | Cartographie : SLAM Toolbox + catalogue de waypoints fermé + Nav2 | L1, L2 | `/map` publiée, 3 waypoints nommés atteints à ±20 cm |
| **L6** | Caméra du poignet dans ROS + skills `search_object`, `grasp_object`, `follow_human` | L2, L5 | 15 Hz sur le topic du poignet ; 10 saisies avec écart-type mesuré ; suivi à 1,0 m maintenu 60 s |
| **L7** | Audio : enceinte BT en sortie, Piper TTS, `express_state` complet | L4 | TTS audible ; VAD sans faux positif sur 10 min de bruit ; LED/buzzer < 100 ms |

Les lots peuvent être livrés dans cet ordre ; L5 et L6 peuvent se chevaucher une fois L2 clos.
Chaque lot reçoit son propre plan détaillé au moment de l'attaquer ; ci-dessous, L1 et L2 sont
détaillés tâche par tâche parce qu'ils conditionnent tout le reste.

---

## Lot 1 — Fondations d'odométrie

### Task 1.1 : Configuration EKF et publication de `/odom`

**Files :**
- Create : `config/ekf.yaml`, `launch/ekf.launch.py`
- Create : `tests/test_ekf_config.py`
- Modify : `services/` (nouvelle unité `clawbot-ekf.service`)

**Interfaces :**
- Consumes : `/vel_raw` (`geometry_msgs/TwistStamped` ou `Twist`), `/imu/data_raw` (`sensor_msgs/Imu`)
- Produces : `/odom` (`nav_msgs/Odometry`), TF `odom → base_link`, paramètres
  `ekf_filter_node.frequency = 30.0`, `two_d_mode = true`, `world_frame = odom`

- [ ] **Step 1 : écrire le test de configuration**

```python
# tests/test_ekf_config.py
import yaml, pathlib

def test_ekf_config_pins_inputs_and_frames():
    cfg = yaml.safe_load(pathlib.Path("config/ekf.yaml").read_text())
    node = cfg["ekf_filter_node"]["ros__parameters"]
    assert node["frequency"] == 30.0
    assert node["two_d_mode"] is True
    assert node["odom_frame"] == "odom"
    assert node["base_link_frame"] == "base_link"
    assert node["world_frame"] == "odom"
    assert node["odom0"] == "/vel_raw"
    assert node["imu0"] == "/imu/data_raw"
    # le gyro compense le glissement des roues Mecanum : le lacet IMU doit être fusionné
    assert node["imu0_config"][5] is True
    # la vitesse en y n'est PAS un bruit : mecanum se déplace latéralement
    assert node["odom0_config"][7] is True
```

- [ ] **Step 2 : lancer le test, vérifier l'échec**

Run : `pytest tests/test_ekf_config.py -v`
Expected : FAIL (`config/ekf.yaml` inexistant)

- [ ] **Step 3 : créer `config/ekf.yaml` et `launch/ekf.launch.py`**

Valeurs imposées : `frequency: 30.0`, `two_d_mode: true`, `odom0: /vel_raw`, `imu0: /imu/data_raw`,
`odom0_differential: false`, `imu0_differential: false`, `publish_tf: true`, `world_frame: odom`.
Le lancement démarre `robot_localization/ekf_node` avec ce fichier.

- [ ] **Step 4 : installer la dépendance manquante**

Run : `sudo apt install -y ros-humble-robot-localization`
Expected : paquet présent, `ros2 pkg prefix robot_localization` renvoie un chemin (il est **absent**
aujourd'hui).

- [ ] **Step 5 : vérifier le test**

Run : `pytest tests/test_ekf_config.py -v`
Expected : PASS

- [ ] **Step 6 : essai réel sur le robot (opérateur présent)**

Run : `ROS_DOMAIN_ID=28 ros2 launch launch/ekf.launch.py` puis
`ros2 run tf2_ros tf2_echo odom base_link` et `ros2 topic hz /odom`
Expected : `/odom` ≥ 25 Hz, TF publiée, position qui varie quand on pousse le robot à la main.

- [ ] **Step 7 : commit**

```bash
git add config/ekf.yaml launch/ekf.launch.py tests/test_ekf_config.py
git commit -m "feat(odom): fusion EKF vel_raw + IMU, publication /odom et TF odom->base_link"
```

### Task 1.2 : Mesure de dérive (critère de sortie du lot)

**Files :**
- Create : `scripts/measure_odom_drift.py`
- Create : `tests/test_measure_odom_drift.py`

**Interfaces :**
- Consumes : `/odom`, TF `odom→base_link`
- Produces : `measure_drift(samples: list[tuple[float, float, float]]) -> dict` avec
  `{"distance_m": float, "lateral_m": float, "yaw_deg": float, "drift_pct": float}`

- [ ] **Step 1 : test du calcul de dérive (données synthétiques, sans ROS)**

```python
def test_drift_zero_on_straight_line():
    samples = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    result = measure_drift(samples)
    assert result["distance_m"] == 2.0
    assert result["lateral_m"] == 0.0
    assert result["drift_pct"] == 0.0

def test_drift_counts_lateral_error():
    samples = [(0.0, 0.0, 0.0), (1.0, 0.03, 0.0), (2.0, 0.05, 0.0)]
    assert round(measure_drift(samples)["drift_pct"], 1) == 2.5
```

- [ ] **Step 2 : lancer, vérifier l'échec** — `pytest tests/test_measure_odom_drift.py -v` → FAIL

- [ ] **Step 3 : implémenter `measure_drift`** — dérive = `max(|y|) / distance` × 100, yaw final en degrés

- [ ] **Step 4 : test vert** — `pytest tests/test_measure_odom_drift.py -v` → PASS

- [ ] **Step 5 : essai physique** — 2 m en ligne droite au clavier, enregistrer `/odom`, calculer.
  Expected : `drift_pct < 5.0`. Au-delà, ne pas passer au lot 2 : corriger d'abord l'échelle.

- [ ] **Step 6 : commit** — `feat(odom): mesure de derive, critere de sortie du lot 1`

### Task 1.3 : ERR-009 — proportionnalité de la consigne

**Files :**
- Modify : `yahboomcar_bringup/yahboomcar_bringup/Mcnamu_driver_X3.py` (échelle de trame)
- Create : `tests/test_cmd_vel_scaling.py`

**Interfaces :**
- Consumes : `/cmd_vel` (`geometry_msgs/Twist`)
- Produces : `scale_cmd_vel(twist, max_linear: float, max_angular: float) -> tuple[int, int, int]`
  (trame MCU `vx, vy, wz` en unités entières)

- [ ] **Step 1 : test de proportionnalité**

```python
def test_half_command_gives_half_frame():
    full = scale_cmd_vel(Twist(linear=Vector3(x=0.2)), 0.2, 1.0)
    half = scale_cmd_vel(Twist(linear=Vector3(x=0.1)), 0.2, 1.0)
    assert full[0] == 1000
    assert half[0] == 500

def test_deadband_does_not_leak_motion():
    assert scale_cmd_vel(Twist(linear=Vector3(x=0.001)), 0.2, 1.0)[0] == 0
```

- [ ] **Step 2 : FAIL attendu** — `pytest tests/test_cmd_vel_scaling.py -v`

- [ ] **Step 3 : implémenter `scale_cmd_vel`** dans le driver, seuil mort à 1 % de la commande max

- [ ] **Step 4 : PASS attendu**

- [ ] **Step 5 : essai physique (opérateur, espace dégagé)** — consigne 0,1 m/s pendant 2 s, mesurer
  la distance réelle. Expected : 0,20 m ± 10 %. Si l'écart persiste, vérifier le **type de robot en
  flash MCU** (Mecanum X3 vs différentiel) avant de toucher au code.

- [ ] **Step 6 : commit** — `fix(err-009): echelle de commande proportionnelle et seuil mort`

---

## Lot 2 — Proprioception et arbitre réflexe

### Task 2.1 : Logique de seuils, sans ROS

**Files :**
- Create : `clawbot_safety/clawbot_safety/thresholds.py`, `clawbot_safety/package.xml`,
  `clawbot_safety/setup.py`
- Create : `clawbot_safety/test/test_thresholds.py`

**Interfaces :**
- Produces :
  - `tilt_state(roll_deg: float, pitch_deg: float, servo2_deg: float) -> str` → `"ok"`,
    `"hold"` (≥ 8°), `"drop_torque"` (≥ 12° **et** `servo2_deg < 95`), `"freeze"` (≥ 12° et
    `servo2_deg >= 95`)
  - `obstacle_stop(front_m: float, cmd_nonzero: bool) -> bool` (vrai si < 0.15 m et commande non nulle)
  - `battery_state(samples: list[float], now_s: float) -> str` → `"ok"`, `"low"` (< 10.5 V hors pic)
  - `is_stale(age_s: float, limit_s: float = 2.0) -> bool`

- [ ] **Step 1 : tests des quatre seuils, valeurs de la spec**

```python
def test_tilt_hold_at_eight_degrees():
    assert tilt_state(0.0, 7.9, 90) == "ok"
    assert tilt_state(0.0, 8.1, 90) == "hold"

def test_torque_cut_only_when_arm_is_forward():
    assert tilt_state(0.0, 12.5, 70) == "drop_torque"   # extension avant : chute vers le sol
    assert tilt_state(0.0, 12.5, 96) == "freeze"        # relevé arrière : chute contre le mât

def test_invalid_angle_is_treated_as_stop():
    assert tilt_state(float("nan"), 0.0, 90) == "hold"
    assert tilt_state(0.0, -5.0, 90) == "hold"   # cas réel servo 4 à -5°

def test_obstacle_stop_needs_motion():
    assert obstacle_stop(0.12, True) is True
    assert obstacle_stop(0.12, False) is False

def test_battery_ignores_motor_current_spike():
    samples = [11.9] * 20 + [10.4]   # pic transitoire en fin de fenêtre
    assert battery_state(samples, now_s=10.0) == "ok"
```

- [ ] **Step 2 : FAIL attendu** — `pytest clawbot_safety/test/test_thresholds.py -v`

- [ ] **Step 3 : implémenter `thresholds.py`** — fonctions pures, aucune dépendance ROS, aucune
  allocation en boucle. La moyenne glissante batterie porte sur **10 s** et le pic est écarté si sa
  durée est < 2 s.

- [ ] **Step 4 : PASS attendu** — les cinq tests verts.

- [ ] **Step 5 : commit** — `feat(safety): seuils purs (basculement, obstacle, batterie, peremption)`

### Task 2.2 : Lecture servo entrelacée dans le driver

**Files :**
- Modify : `yahboomcar_bringup/yahboomcar_bringup/Mcnamu_driver_X3.py`
- Create : `tests/test_servo_round_robin.py`
- Create : `clawbot_safety/clawbot_safety/round_robin.py`

**Interfaces :**
- Consumes : le tick du driver à 10 Hz, l'accès série existant
- Produces : `RoundRobin(servo_ids: list[int], period_ticks: int, idle_period_ticks: int)` avec
  `next_servo(tick: int, arm_at_rest: bool) -> int | None` ; topic publié
  `/arm/servo_angles` (`std_msgs/Int32MultiArray`, 6 valeurs, ordre `servo1..servo6`)

- [ ] **Step 1 : test du planificateur**

```python
def test_one_servo_per_tick_when_active():
    rr = RoundRobin([1, 2, 3, 4, 5, 6], period_ticks=1, idle_period_ticks=10)
    assert [rr.next_servo(t, False) for t in range(6)] == [1, 2, 3, 4, 5, 6]
    assert rr.next_servo(6, False) == 1          # cycle complet en 600 ms à 10 Hz

def test_servo_read_is_skipped_at_rest():
    rr = RoundRobin([1, 2, 3, 4, 5, 6], period_ticks=1, idle_period_ticks=10)
    assert rr.next_servo(0, True) == 1
    assert rr.next_servo(1, True) is None        # 1 Hz seulement quand le bras est au repos

def test_tick_budget_is_respected():
    rr = RoundRobin([1, 2, 3, 4, 5, 6], period_ticks=1, idle_period_ticks=10)
    # une lecture = ~20 ms sur un tick de 100 ms : on ne doit jamais en faire deux
    assert all(rr.next_servo(t, False) is not None for t in range(3))
```

- [ ] **Step 2 : FAIL attendu**

- [ ] **Step 3 : implémenter `RoundRobin`** puis brancher la lecture dans le tick du driver :
  1 servo par tick, publication de `/arm/servo_angles` avec la valeur fraîche et les 5 précédentes
  conservées ; à `-1` (invalide) la valeur n'est pas publiée telle quelle mais marquée `-1` pour que
  l'arbitre applique `test_invalid_angle_is_treated_as_stop`.

- [ ] **Step 4 : test du planificateur vert**

- [ ] **Step 5 : vérifier que la boucle n'est pas cassée (critère du lot)**

Run (robot, domaine 28) :
```bash
ros2 topic hz /imu/data_raw & ros2 topic hz /vel_raw & ros2 topic hz /arm/servo_angles
```
Expected : `/imu` et `/vel_raw` ≥ 9,5 Hz **pendant** les lectures servo ; `/arm/servo_angles`
cycle complet en ~600 ms. Si `/imu` tombe sous 9,5 Hz : réduire à 2 ticks par lecture.

- [ ] **Step 6 : commit** — `feat(driver): proprioception des servos entrelacée, sans casser les 10 Hz`

### Task 2.3 : Nœud arbitre et propriété de `/cmd_vel`

**Files :**
- Create : `clawbot_safety/clawbot_safety/arbitrator.py`
- Create : `clawbot_safety/test/test_arbitrator.py`
- Create : `services/clawbot-safety-arbitrator.service`
- Modify : `ros2_llm_bridge/hardware_service.py` (retrait des endpoints de mouvement)

**Interfaces :**
- Consumes : `/imu/data_raw`, `/scan`, `/voltage`, `/arm/servo_angles`, `/cmd_vel` (entrée)
- Produces : `/cmd_vel_safe` (sortie unique vers le MCU), `/safety/hold` (`std_msgs/Bool`),
  `/safety/state` (`std_msgs/String`, valeurs `OK|HOLD|STOP|BATTERY_LOW|SENSOR_STALE`)

- [ ] **Step 1 : test d'intégration en domaine 99 (topics factices)**

```python
def test_obstacle_forces_zero_within_100ms(arbitrator_node):
    publish("/cmd_vel", Twist(linear=Vector3(x=0.2)))
    publish("/scan", scan_with_front_obstacle(0.12))
    speeds = collect("/cmd_vel_safe", duration=0.5)
    assert speeds[-1].linear.x == 0.0
    assert time_to_zero(speeds) < 0.1
    assert last_state(arbitrator_node) == "STOP"

def test_stale_scan_does_not_silence_the_guard(arbitrator_node):
    # /scan muet : le garde-fou ne peut pas se taire, il doit signaler la perte
    publish("/cmd_vel", Twist(linear=Vector3(x=0.2)))
    assert wait_for_state(arbitrator_node, "SENSOR_STALE", timeout=2.5)
```

- [ ] **Step 2 : FAIL attendu** — `ROS_DOMAIN_ID=99 pytest clawbot_safety/test/test_arbitrator.py -v`

- [ ] **Step 3 : implémenter l'arbitre** — timer 20 Hz, aucune allocation en boucle, appels à
  `thresholds.py` uniquement. Il publie `/cmd_vel_safe`, jamais `/cmd_vel`. Mesure de gigue à
  journaliser ; si p99 > 50 ms, basculer le nœud en C++ (décision du §11 de la spec).

- [ ] **Step 4 : PASS attendu**

- [ ] **Step 5 : rendre la propriété unique vraie** — le driver s'abonne à `/cmd_vel_safe` ;
  les endpoints de mouvement de `:8001` répondent `410 Gone` (la capture reste) ; `joy_teleop` est
  arrêté et désactivé en attendant une manette.

- [ ] **Step 6 : vérifier sur le robot**

Run : `ros2 topic info /cmd_vel_safe` → `Publisher count: 1`.
Expected : 1 éditeur, et l'arrêt d'urgence physique toujours fonctionnel.

- [ ] **Step 7 : commit** — `feat(safety): arbitre 20 Hz, propriete unique de /cmd_vel_safe`

---

## Lots 3 à 7 — jalons (plan détaillé écrit au démarrage de chaque lot)

- **L3 Directeur** : `clawbot_director` (rclpy, `asyncio` ou timer), registre `task_id`,
  préconditions, exécution de séquence JSON (6 étapes max), états `IDLE|RUNNING|WAITING_CONFIRMATION|DONE|FAILED`,
  codes `BUSY|PRECONDITION_FAILED|CANCELLED_SAFETY|TIMEOUT`. Sortie : second skill refusé, annulation
  < 200 ms.
- **L4 Sentinel** : machine `IDLE/WATCHING/ENGAGED`, VAD Silero, YOLO à 1-2 Hz avec hystérésis
  2 frames et `depth < 3,5 m`, cooldowns (60 s visuel, 5 s audio), mots d'arrêt locaux inconditionnels,
  `oui`/`non` captés seulement en `WAITING_CONFIRMATION`, réveil S2 par webhook permanent.
- **L5 Cartographie** : `slam_toolbox` en ligne, `catalogue_waypoints.yaml` en énumération fermée,
  Nav2 avec le BT standard, `navigate_to` refusant les chaînes libres.
- **L6 Perception et skills** : `v4l2_camera_node` en 640×480 à 15 Hz, `wrist_camera_optical_frame`
  dans l'URDF, `search_object` (paliers de 45°), `grasp_object` (boucle fermée, tolérance 1-2 cm,
  répétabilité mesurée sur 10 saisies), `follow_human` (désignation, suivi 10-15 Hz, distance 1,0 m).
- **L7 Audio** : appairage A2DP validé, Piper TTS, `express_state` complet sur `/RGBLight` et
  `/Buzzer` ; STT sur les micros existants (cartes 0 et 1).

## Auto-relecture du plan

- Couverture de la spec : §5.1 → L2 ; §5.2 → L3 ; §5.3 → L4 ; §6 → L3 (contrat) ; §7 → L3 ;
  §8 → L4 ; §9 → L7 ; §10 étapes 1-2 → L1, 2 bis → L5, 3 bis → L2, 4 → L2, 4 bis → L3, 5 → L4,
  6 → L7, 7 → L6. Aucun § sans lot.
- Les trois précisions de l'opérateur sont couvertes : UART entrelacé (Task 2.2, step 5),
  géométrie de la coupure (Task 2.1, `test_torque_cut_only_when_arm_is_forward`), `oui`/`non`
  conditionnels (L4, à détailler).
- Les cinq classes du Review Focus ont chacune leur test dans une tâche de L1-L2, et L3/L4 les
  reprendront pour `BUSY` et l'annulation.
- Proportion : le plan détaille les deux lots fondateurs et jalonne les cinq autres ; chaque lot
  reçoit son plan tâche-par-tâche au moment de l'attaquer, pour ne pas transcrire du code à venir.
