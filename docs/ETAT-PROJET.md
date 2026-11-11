# État du projet Clawbot — reprise de session

**Date** : 2026-11-11, fin de session longue (compactions multiples)
**Branche** : `docs/site-okf-merge`, dernier commit `418aa38`
**Robot** : Clawbot X3 Plus, Jetson Orin NX, ROS 2 Humble, domaine 28

> Ce document est fait pour être lu **au début d'une nouvelle session**, à la place d'un
> historique de conversation. Il dit ce qui marche, ce qui est mesuré, ce qui casse, ce qui
> reste, et dans quel ordre continuer.

---

## 1. Comment reprendre

Ouvrir une nouvelle session et envoyer :

> Lis `/home/jetson/clawbot/docs/ETAT-PROJET.md` et
> `docs/superpowers/specs/2026-11-11-architecture-s1-s2-design.md`, puis reprends au §8
> (prochaines étapes) en commençant par la brique 1.

Ne pas relancer les diagnostics déjà faits : ils sont tous dans ce document avec leurs chiffres.

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
| Proprioception | **nouvelle** | `/arm/servo_angles` 10 Hz, cycle 600 ms, sans casser `/imu` et `/vel_raw` |
| Manipulation | ok | MoveIt planifie et exécute, collision mât modélisée |
| Arbitre réflexe | **actif** | 20 Hz, obstacle 12 cm → zéro en **47 ms**, chien de garde 0,5 s |
| Arrêt du bras par réflexe | **prouvé** | `/safety/hold` → « interrompu par safety hold après 6 échantillons » |
| Directeur | **cœur fait** | task_id, BUSY, préconditions, séquences 6 étapes, 7 tests |
| SLAM | **réparé** | carte 8,1 × 6,5 m, `map→odom` recale 24 cm sur 2,6 m |
| Pont MCP → Hermes | ok | 22 outils, stdio, `hermes mcp test clawbot` liste les 22 |
| Déclenchement S1→S2 | voie CLI | 46,4 s mesuré, webhook prêt (redémarrage passerelle requis) |

**Suite de tests : 174 verts** (pont MCP, seuils, arbitre, contrôleur de bras, EKF, mise à
l'échelle, dérive, round-robin, directeur). Commande exacte :

```bash
cd /home/jetson/clawbot
export ROS_DOMAIN_ID=99
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
source /opt/ros/humble/setup.bash
python3 -m pytest tests/mcp_bridge clawbot_safety/test clawbot_arm_controller/test \
  clawbot_director/test tests/test_ekf_config.py tests/test_cmd_vel_scaling.py \
  tests/test_measure_odom_drift.py tests/test_servo_round_robin.py \
  -p no:launch_testing -p no:launch_ros -o addopts="" -q
```

---

## 3. Ce qui a été corrigé cette session (et pourquoi ça compte)

| Défaut | Cause réelle | Correctif | Commit |
|---|---|---|---|
| Base non proportionnelle, signe inversé, pics à 5,6 × | `set_car_type(1)` **ligne 58 du driver** annulait le passage en X3 Plus | suppression, renvoi de `set_car_type(2)` pendant le boot STM32 | `aad2cf0` |
| `/vel_raw` inutilisable par l'EKF | `geometry_msgs/Twist` nu | ajout de `/odom_raw` en `Odometry` avec covariances | `b1525f2` |
| Dérive fantôme de 0,41 m à l'arrêt | accélération linéaire fusionnée (biais intégré) | `imu0_config` : vitesse de lacet seule | `b1525f2` |
| SLAM muet, `map→odom` figée | `base_frame = base_footprint`, frame inexistante | `base_frame:=base_link` | `8d3a901` |
| Arbitre invisible du graphe, `SENSOR_STALE` permanent | service lancé en **root** → découverte DDS isolée | `User=jetson` | `e77dabf` |
| Robot qui continue d'avancer | dernière consigne republiée à 20 Hz | chien de garde 0,5 s | `e77dabf` |
| Garde-fou décoratif | `canceled()` appelé sans demande cliente → transition invalide, **la trajectoire continuait** | `abort()` pour l'arrêt réflexe | `0984414` |
| Driver qui n'est pas celui du dépôt | service depuis `yahboomcar_ros2_ws`, copie non versionnée | patch porté dans les deux copies | — |

---

## 4. Architecture en place

```text
S2  Hermes ── MCP stdio (22 outils) ──┐        ▲ webhook (réveil, passerelle à redémarrer)
──────────────────────── S1 ──────────┼────────┴──────────────────────────────
  DIRECTOR (logique pure)   ARBITRE 20 Hz          SENTINEL (à faire)
  task_id, séquences        /cmd_vel → /cmd_vel_safe     VAD, YOLO 1-2 Hz
  préconditions             /safety/hold, /safety/state
         │                        │
  serveurs d'action        /cmd_vel_safe ── driver ── MCU ── roues
  (bras, grip)             /safety/hold ── contrôleur de bras (abort)
```

**Topics clés** : `/odom_raw`, `/odom`, `/arm/servo_angles`, `/cmd_vel_safe`, `/safety/hold`,
`/safety/state` (`OK|HOLD|FREEZE|DROP_TORQUE|STOP|SENSOR_STALE|BATTERY_LOW`), `/director/state`
(JSON : état de tâche + dernière valeur de sécurité vue).

**Services systemd actifs** : `ros2-driver-node`, `clawbot-lidar`, `orbbec-camera`,
`clawbot-description`, `clawbot-arm-controller`, `clawbot-move-group`, `clawbot-slam`,
`clawbot-safety-arbitrator`, `clawbot-director`, `clawbot-docs`, `yolo-inference`,
`ros2-hardware-service`, `ros2-llm-bridge-cpp`.

**Paquets créés** : `clawbot_safety` (seuils + arbitre), `clawbot_director` (cœur),
`clawbot_arm_controller`, `clawbot_moveit_config`.

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

---

## 6. Ce qui est cassé ou incomplet

| Point | Gravité | Détail |
|---|---|---|
| `DROP_TORQUE` n'actionne rien | **sécurité** | l'état est publié, le contrôleur s'arrête, mais aucun étage ne coupe le couple des servos (`set_uart_servo_torque`). Décision prise, non appliquée. |
| Directeur à moitié branché | bloquant lot 3 | nœud ROS `clawbot-director` et annulation sur `safety` faits (2,0 ms) ; pas d'outils MCP, `advance()` encore appelé à la main |
| Test d'inclinaison réel | moyen | les seuils sont validés sur IMU **simulée** |
| Temps mort base ~0,85 s | moyen | friction statique du MCU, insuffisant pour un asservissement visuel |
| Endpoints de mouvement `:8001` | faible | publient encore sur `/cmd_vel` (2e écrivain) |
| `joy-teleop` actif sans manette | faible | à arrêter |
| Caméra du bras hors graphe | moyen | seule la voie OpenCV la voit |
| Passerelle webhook | faible | configurée, pas active (`hermes gateway restart --yes` demandé) |

---

## 7. Pièges appris (à ne pas repayer)

1. **Un service systemd lancé en root est invisible du graphe ROS** : découverte DDS isolée.
   Toujours `User=jetson`. Et `Environment=HOME=/home/jetson` obligatoire, sinon rclpy meurt sur
   `Failed to get logging directory`.
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
9. **Jamais `ROS_DOMAIN_ID=28` pendant les tests** (ENV-01) : 99 uniquement.

---

## 8. Prochaines étapes, dans l'ordre

### Brique 1 — nœud ROS du directeur (courte, sans matériel) — **faite**
`clawbot_director/director_node.py` : instancie `Director`, s'abonne à `/safety/state` et annule
la tâche dès que l'état sort de `OK`, publie `/director/state`. Test domaine 99 : état
`/safety/state` à `STOP` → tâche `CANCELLED_SAFETY` en < 200 ms.
Mesuré : **2,0 ms médian, 2,5 ms max** sur 5 essais (domaine 99, DDS local). Service
`clawbot-director` actif en domaine 28, `/director/state` publié à 5 Hz même sans changement
(un abonné tardif doit voir l'état). Reste pour la brique 2 : rien ne peut encore démarrer de
tâche dans ce nœud — c'est la surface MCP qui l'ouvrira.

### Brique 2 — surface MCP
Trois outils dans `bridge_mcp` : `start_skill(skill, args)`, `get_task()`, `cancel_task(task_id)`.
Le directeur devient accessible à S2, qui déclare des séquences au lieu de piloter des topics.
Ajouter les tests contractuels (le pont en a déjà 22 outils, l'enveloppe est réutilisable).

### Brique 3 — accrochage aux actions réelles
`advance()` doit être appelé par la fin d'un goal : `FollowJointTrajectory` pour le bras,
`NavigateToPose` pour la base. C'est ce qui permet « va là, prends ça, reviens ».

### Puis
4. Sentinel : VAD, YOLO 1-2 Hz, mots d'arrêt locaux, réveil S2 par webhook.
5. Cartographie dense + Nav2 + catalogue de waypoints fermé.
6. Caméra du poignet dans ROS + `search_object`, `grasp_object`, `follow_human`.
7. Audio : A2DP sortie, Piper TTS, `express_state`.

### Dettes à traiter en parallèle
- actionner `DROP_TORQUE` (coupe de couple servo) — opérateur présent.
- test d'inclinaison réel.
- arrêter `joy-teleop`, déprécier les endpoints de mouvement de `:8001`.

---

## 9. Commandes utiles

```bash
# état des services
systemctl is-active ros2-driver-node clawbot-safety-arbitrator clawbot-arm-controller \
  clawbot-slam clawbot-docs

# chaîne de sécurité
ros2 topic echo /safety/state --once
ros2 topic hz /arm/servo_angles

# base
ROS_DOMAIN_ID=28 python3 scripts/base_probe_l1.py --speed 0.05 --duration 3

# preuve réflexe -> bras (domaine 99, sûr)
ROS_DOMAIN_ID=99 python3 scripts/test_safety_hold.py

# documentation
sudo systemctl restart clawbot-docs && curl -s -o /dev/null -w '%{http_code}\n' \
  http://127.0.0.1:8080/knowledge-base/02_Software/systeme1_arbitre/
```

## 10. Documentation

- Base OKF : `/Robot_Knowledge_Base` (50 fichiers, 0 erreur), publiée sur `:8080`.
- Conception : `docs/superpowers/specs/2026-11-11-architecture-s1-s2-design.md`
- Plan : `docs/superpowers/plans/2026-11-11-architecture-s1-s2.md`
- Pages clés : `inventaire_materiel`, `slam_cartographie`, `systeme1_arbitre`, `mcp_hermes`,
  `manipulation_moveit`, `ERR-2026-11-11-010_base_non_proportionnelle`
