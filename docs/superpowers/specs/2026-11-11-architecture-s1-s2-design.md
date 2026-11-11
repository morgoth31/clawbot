---
title: "Architecture S1/S2 du Clawbot X3 Plus — conception"
date: 2026-11-11
status: proposé
auteur: "Hermes Agent, avec l'opérateur"
---

# Architecture S1 / S2 du Clawbot X3 Plus

## 1. Intention et pourquoi

Le robot doit interagir avec des humains, comprendre une demande et l'exécuter en s'adaptant au
contexte. Trois entrées : la voix, les images de personnes, Telegram. Sept tâches visées : se
déplacer, cartographier, attraper, chercher, transporter, suivre une personne, jouer aux échecs.

Le obstacle n'est pas la puissance de raisonnement, c'est le **temps**. Mesures du 2026-11-11 :

| Chaîne | Latence mesurée | Conséquence |
|---|---|---|
| Déclenchement S2 par CLI, contexte complet | **46,4 s** | inutilisable pour une interaction |
| Réponse triviale de S2 (session + aller-retour cloud) | **7,0 s** | plancher d'une décision S2 |
| Réveil par webhook (acceptation HTTP) | < 500 ms | mais la décision reste à 4-7 s |
| Inférence YOLO (:8003) | 279 ms | exploitable à 1-2 Hz en veille |
| Boucle de l'arbitre réflexe | 20 Hz (50 ms) | seule échelle compatible avec la sécurité |

**Principe directeur** : S2 ne doit jamais être dans la boucle de contrôle. S1 exécute, surveille
et interrompt ; S2 planifie, arbitre le sens, et se réveille sur événement.

## 2. Contraintes matérielles mesurées

| Élément | État réel | Ce que ça interdit |
|---|---|---|
| `/odom` et `odom→base_link` | **absents** | Nav2, SLAM en boucle fermée, « va à un endroit », suivi de personne |
| Base Mecanum, ERR-009 | consigne non proportionnelle | déplacement fin, asservissement visuel de la base |
| Bras 5 axes + pince | opérationnel, ±1° | — |
| Seuil de collision mât | contact physique à servo 2 ≈ 114°, refus du modèle à 105-106°, marge 0,02 m | approche du mât sans garde-fou logiciel |
| Caméra du bras `0c45:6340` | présente, **aucun nœud ROS** | asservissement visuel final, vérification de saisie |
| Astra Pro+ | couleur 20,06 Hz, profondeur 29,99 Hz, IR 29,97, points 29,08 | — |
| TG30 | `/scan` 10,082 Hz | — |
| **Haut-parleur** | **aucun** (HDMI seulement) | toute parole du robot |
| Micros | carte 0 (UVC) et carte 1 (Astra), 48 kHz | — |
| `/cmd_vel` | **2 éditeurs, 1 abonné** | ajouter un écrivain sans arbitrage rend les garde-fous décoratifs |
| Pile audio | PulseAudio 15.99, Bluetooth Realtek `0bda:c822` débloqué | A2DP non validé en réel |
| Contrôleur de bras | **accepte l'annulation** (`CancelResponse.ACCEPT`, `is_cancel_requested`) | rien — l'avortement est possible aujourd'hui |
| Graphe | 15 nœuds, 38 topics, domaine 28 | — |

## 3. Objectifs, non-objectifs, anti-objectifs

**Objectifs**

- Une demande vocale ou Telegram produit une action dans la seconde (accusé S1) et une réponse
  complète en 5 à 10 s (S2 asynchrone).
- Aucune commande de S2 ne peut dépasser un garde-fou réflexe : S1 a toujours le dernier mot.
- Le robot reste utilisable réseau coupé, en mode dégradé (commandes connues seulement).
- Toute décision est traçable : qui a demandé, quel skill, quel `task_id`, pourquoi annulé.
- Chaque point de rupture du §2 est fermé par une étape mesurable.

**Non-objectifs (pour cette version)**

- Autonomie longue sans opérateur : l'opérateur reste présent lors des essais physiques.
- Apprentissage en ligne, ajustement de politique, RL.
- Navigation 3D ou tout-terrain.
- Échecs en compétition : un échiquier, pièces légères, niveau loisir.

**Anti-objectifs** (réussite technique mais échec réel)

- Un robot qui obéit vite mais qu'on ne peut pas arrêter.
- Un S2 qui décide à partir d'un contexte périmé et envoie des coordonnées absolues.
- Des garde-fous qui vivent dans le même ordonnanceur que la planification : un calcul MoveIt
  ne doit jamais retarder un arrêt anti-basculement.
- Une surface d'édition laissée à S2 qui soit un arbre exécutable plutôt que des données.

## 4. Approches considérées

**A — BehaviorTree.CPP partout**, navigation incluse via le BT Navigator de Nav2. Un seul moteur
de composition, halt hiérarchique natif, S2 peut réécrire un XML.
*Rejetée* : C++ obligatoire pour chaque skill, et surtout S2 éditerait l'arbre qui contient la
sûreté. Le point d'édition et le point de sécurité deviennent le même fichier.

**B — Skills en serveurs d'action Python, directeur asyncio maison, sans Nav2 BT.**
Construit sur l'existant (`arm_trajectory_server` est déjà un serveur d'action, `bridge_mcp` est
Python), tests faciles.
*Rejetée* : il faut réécrire composition, concurrence et halt, et la navigation finira par
réimplémenter ce que Nav2 fait déjà.

**C — Hybride (retenue).** Nav2 garde son BT interne pour la navigation. Nos skills sont des
serveurs d'action Python. Un **directeur** mince séquence les skills sur un état explicite en
JSON. L'**arbitre réflexe** est un nœud séparé à 20 Hz, hors du chemin de planification, avec le
dernier mot sur `/cmd_vel` et les annulations.

Pourquoi C : la couche réflexe ne partage jamais un ordonnanceur avec la planification, et la
surface d'édition offerte à S2 est faite de **données** (JSON), pas d'un arbre exécutable.

## 5. Architecture retenue

```text
S2  Hermes  ── MCP stdio (intentions) ──┐        ▲ webhook JSON (réveil)
                                        │        │
──────────────────────────── S1 ────────┼────────┴──────────────────────────
  ┌──────────────┐   ┌──────────────┐   │   ┌──────────────────────────────┐
  │  DIRECTEUR   │◄──┤  ARBITRE     │   └──►│  SENTINEL (attention)        │
  │ état JSON    │   │  20 Hz        │      │  VAD · YOLO 1-2 Hz · Telegram│
  │ task_id      │   │  priorités    │      │  transitions + cooldown      │
  │ préconditions│   │  /cmd_vel     │      └──────────────────────────────┘
  └──────┬───────┘   │  annulations  │
         │           └──────┬────────┘
         ▼                  ▼
  ┌──────────────────────────────────────┐
  │ SKILLS (serveurs d'action Python)    │
  │ navigate_to · follow_human ·         │
  │ grasp_object · search_object ·       │
  │ express_state · look_at_board        │
  └──────────────┬───────────────────────┘
                 ▼
  ┌──────────────────────────────────────┐
  │ Nav2 · MoveIt 2 · Perception · Drivers│
  └──────────────────────────────────────┘
```

### 5.1 Arbitre réflexe (`clawbot_safety_arbitrator`)

Nœud séparé, 20 Hz, sans allocation ni planification. Il possède la sortie vers le MCU.

| Garde-fou | Déclencheur | Action |
|---|---|---|
| Anti-basculement | tangage ou roulis > 8° pendant un skill de manipulation | `goal_cancel` sur `/arm_controller`, repli en posture sûre, alerte `CRITICAL_TILT_ABORT` |
| Anti-collision basse | obstacle < 15 cm dans le vecteur de déplacement et `/cmd_vel` non nul | consigne de vitesse écrasée à zéro |
| Mutex bras/base | bras hors enveloppe d'inertie nominale | nav interdite pendant le skill ; bras interdit pendant une trajectoire de base |
| Batterie | < 10,5 V hors appel de courant (moyenne glissante 10 s) | refus des nouveaux déplacements, réveil de S2 |
| Série | perte du lien MCU | consigne nulle, verrou, alerte |

Contrainte d'insertion : `/cmd_vel` a aujourd'hui 2 éditeurs pour 1 abonné. L'arbitre devient
**propriétaire unique** de la sortie (twist_mux en amont, driver en aval). Aucun autre nœud ne
publie vers le MCU.

### 5.2 Directeur

Un seul skill actif à la fois ; registre explicite :

```json
{"task_id": "t-20261111-0017", "skill": "grasp_object", "referent": "tasse rouge sur la table",
 "state": "RUNNING", "started_at": 1794380012.4, "checkpoint": "approche_pre_saisie",
 "preempt_at": "fin_segment"}
```

Responsabilités : valider les préconditions avant exécution, tenir le `task_id`, accepter ou
refuser une préemption, publier l'état pour S2 et pour la supervision. Il ne décide jamais du
sens d'une tâche : il l'exécute et rend compte.

### 5.3 Sentinel (filtre d'attention)

Machine à états `IDLE → WATCHING → ENGAGED`, avec hystérésis et cooldown par canal.

| Canal | Échantillonnage | Règle de transition |
|---|---|---|
| Visuel | YOLO :8003 à 1-2 Hz | `person` confiance > 0,75 **et** profondeur < 3,5 m, sur 2 frames consécutives |
| Audio | VAD Silero continu (CPU) | activité détectée → bip + LED bleue en < 100 ms, puis transcription |
| Telegram | événement | routage direct vers le webhook |
| Anomalie S1 | événement | `PLANNING_FAILED`, blocage, bascule IMU, chute de tension |

Le sentinel ne réveille que sur **transition d'état**, jamais en continu. Cooldown par canal
(60 s visuel, 5 s audio) pour éviter l'orage de réveils.

## 6. Contrat MCP : des intentions, pas de la plomberie

| Outil | Sémantique | Garde-fous S1 |
|---|---|---|
| `get_world_context()` | agrège pose, tension, objets vus (label, confiance, distance, xyz), état pince, tâche en cours, péremption de chaque flux | refuse si un flux indispensable est plus vieux que 2 s |
| `navigate_to(destination)` | `destination` = waypoint cartographié **ou** référent symbolique ; jamais un couple (x, y) libre | perte de TF, pare-chocs lidar, timeout |
| `follow_human(target_id)` | asservissement visuel, distance de sécurité 1,0 m | arrêt si perte visuelle > 2 s |
| `grasp_object(referent)` | localise Astra 3D → approche MoveIt → asservissement UVC → fermeture | IMU anti-basculement, blocage servo, collision mât |
| `search_object(label)` | balayage par paliers de 45° ou patrouille | timeout, batterie |
| `set_watch_mode(rules)` | configure les déclencheurs du sentinel | bras replié, servo en passif si inactif |
| `express_state(state)` | `THINKING`, `LISTENING`, `ERROR`, `SUCCESS`, `WATCHING` sur LED + buzzer | — |
| `cancel_task(task_id)` | annule au prochain point sûr | toujours autorisé |
| `get_task(task_id)` | état, checkpoint, raison d'échec | — |

Règles de contrat, non négociables :

1. **Intention, pas coordonnée.** S2 nomme un référent ; S1 résout la pose au moment d'agir. Un
   couple (x, y) n'est accepté que vers un waypoint cartographié, immuable par construction.
2. **`task_id` obligatoire** en retour de tout skill ; l'état est interrogeable et annulable.
3. **Préconditions vérifiées par S1**, jamais par S2 : pince vide avant `grasp_object`, bras replié
   avant un déplacement, tension au-dessus du seuil. Échec → `PRECONDITION_FAILED`, rien n'est
   exécuté.
4. **Un seul skill actif.** Un second appel reçoit `BUSY` avec le `task_id` courant.
5. Codes stables : `PRECONDITION_FAILED`, `BUSY`, `CANCELLED_SAFETY`, `TIMEOUT`, `ROS_UNAVAILABLE`.

## 7. Priorités et préemption

**0 — sécurité** : arrêt réflexe, toujours immédiat.
**1 — voix / Telegram** : préempte au **prochain point sûr** (fin de segment de trajectoire, base
arrêtée, pince immobile), ou immédiatement si le skill n'a pas encore engagé de mouvement.
**2 — tâche en cours** : continue.
**3 — opportuniste** (exploration, veille active).

Jamais de préemption au milieu d'une fermeture de pince ni pendant une montée en charge.

## 8. Réveil de S2 — payload

```json
{"trigger_type": "EVENT_WAKEUP", "source": "AUDIO_VAD", "timestamp": 1794380000.12,
 "event_data": {"transcription": "…", "speaker_direction_rad": 0.35},
 "robot_snapshot": {"battery_v": 11.85, "mode": "WATCHING",
   "visible_objects": [{"label": "person", "confidence": 0.91, "distance_m": 1.8}],
   "streams": {"/scan": {"hz": 10.1, "age_s": 0.1}, "/camera/color": {"hz": 20.0, "age_s": 0.05}},
   "front_camera_frame": "/tmp/snapshots/astra_latest.jpg",
   "wrist_camera_frame": "/tmp/snapshots/wrist_latest.jpg"}}
```

Règle : le snapshot est un **relevé daté**, jamais une conclusion. Chaque flux porte son âge.

## 9. Audio

- **Sortie** : enceinte Bluetooth en A2DP, Piper TTS local. L'A2DP est unidirectionnel : si le
  micro de l'enceinte est utilisé, la liaison retombe en HFP (mono, bande étroite, +150-300 ms) et
  partage la radio 2,4 GHz avec le Wi-Fi.
- **Entrée** : micros existants, carte 0 (UVC) et carte 1 (Astra), 48 kHz, VAD Silero +
  faster-whisper tiny. L'enceinte ne sert qu'à parler.
- **Court terme sans matériel** : LED + buzzer comme feedback non verbal immédiat (voir
  `express_state`), réponse textuelle sur Telegram.

## 10. Résolution des points de rupture, par ordre de dépendance

| Étape | Contenu | Critère de sortie mesurable |
|---|---|---|
| 1 | Odométrie : intégration de `/vel_raw` + fusion `robot_localization` (EKF, gyro pour le glissement Mecanum) | `/odom` et `odom→base_link` publiés, dérive < 5 % sur 2 m en ligne droite |
| 2 | ERR-009 : type de robot en flash MCU (Mecanum X3) et échelle de trame `set_car_motion` | consigne 0,1 m/s → vitesse mesurée dans ±10 % |
| 3 | Caméra du bras dans ROS : `v4l2_camera_node` en 640×480 à 15 Hz, `wrist_camera_optical_frame` dans l'URDF sur `arm_link5` | topic publié à 15 Hz, TF cohérent, image vérifiée |
| 4 | Arbitre réflexe + propriété de `/cmd_vel` | arrêt à obstacle < 15 cm en < 100 ms, journalisé |
| 4 bis | Directeur, `task_id`, préconditions, `cancel_task` | deux skills concurrents refusés proprement ; annulation en < 200 ms |
| 5 | Sentinel + webhook permanent | réveil S2 < 500 ms côté acceptation, décision < 10 s, aucun réveil en double |
| 6 | Audio | TTS audible, VAD déclenche le sentinel sans faux positif sur 10 min de bruit |
| 7 | Skills hauts niveaux, dans l'ordre : `search_object` → `grasp_object` → `follow_human` → échecs | chacun validé par un essai physique tracé |

Détail utile : `arm_trajectory_server` accepte déjà `CancelResponse.ACCEPT`; l'avortement
anti-basculement ne dépend donc que de l'arbitre et du jeton de contrôle, pas d'une réécriture.

## 11. Ce qui est laissé à l'implémenteur

- Langage de l'arbitre : C++ (rclcpp) recommandé pour la latence déterministe ; Python acceptable
  si le nœud reste sans allocation en boucle.
- Implémentation du directeur : processus Python unique avec `asyncio`, ou nœud rclpy ; le contrat
  JSON ne change pas.
- Choix du moteur VAD/STT (Silero + faster-whisper tiny proposé) et du TTS (Piper proposé).
- Découpage exact des paliers de `search_object` et de `look_at_board`.
- Format des snapshots et politique de rétention.
- Stratégie de test : `ROS_DOMAIN_ID=99` obligatoire, jamais 28 pendant les tests.

## 12. Décisions prises dans la conversation

1. Approche **C** (hybride Nav2 + directeur JSON + arbitre séparé), pour ne pas partager
   d'ordonnanceur entre réflexe et planification.
2. S2 envoie des **intentions**, pas des coordonnées.
3. **`task_id`** et registre de tâche unique.
4. **Préconditions vérifiées par S1**, S2 n'est jamais cru.
5. Échelle de priorité **0 > 1 > 2 > 3**, préemption au prochain point sûr.
6. Enceinte Bluetooth en **sortie seule**, STT sur les micros existants.
7. Mode dégradé hors ligne conservé (S1 traite les commandes connues, S2 est un bonus).
