---
type: Mode Specification
title: "Modes de Fonctionnement du Clawbot"
description: "Specification des 4 modes: NAVIGATION, MANIPULATION, EVOLUTION, STANDBY. Chaque mode definit les sous-systemes actifs, les tools disponibles, et les transitions."
status: draft
tags: [modes, specification, architecture, state-machine]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-11T00:30:00Z
---

# Modes de Fonctionnement du Clawbot

## Vue d'Ensemble

Le robot opere dans 4 modes mutuellement exclusifs. Chaque mode active/desactive
des sous-systemes (SLAM, cameras, bras, YOLO) et expose un sous-ensemble des 17 tools.
Les transitions entre modes sont geres par le mode_manager.

```
                    +------------------+
                    |     STANDBY      |
                    | (mode par defaut) |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
     +--------+----+ +------+------+ +------+--------+
     | NAVIGATION  | | MANIPULATION| |   EVOLUTION   |
     | SLAM + LiDAR| | 3DCam + Bras| | Self-modify   |
     | Nav2 + Map  | | YOLO + Claw | | Code + Tests  |
     +-------------+ +-------------+ +---------------+
```

## Mode 1: NAVIGATION

### Description
Mode de deplacement autonome et de cartographie. Le robot utilise le LiDAR
pour SLAM 2D (Cartographer) et/ou la camera 3D Orbbec pour SLAM 3D (RTAB-Map).
Navigation autonome via Nav2 vers des coordonnees cibles.

### Sous-systemes actifs

| Sous-systeme | Etat | Usage |
|-------------|------|-------|
| Driver node (roues) | ACTIF | cmd_vel -> serial |
| LiDAR YDLIDAR | ACTIF | /scan -> SLAM |
| Cartographer SLAM | ACTIF | /map (OccupancyGrid) |
| Camera 3D Orbbec | OPTIONNEL | depth -> costmap 3D |
| Camera front (video0) | OPTIONNEL | Analyse scene pendant navigation |
| Nav2 | ACTIF (si carte disponible) | NavigateToPose action |
| Hardware service | ACTIF | Safety limits, watchdog |
| Joy teleop | OPTIONNEL | Override manuel |

### Tools disponibles (13/17)

| Tool | Disponible | Notes |
|------|-----------|-------|
| SetVelocity | OUI | Deplacement manuel (LiDAR safety ON) |
| Stop | OUI | Arret immediat |
| NavigateTo | OUI | Nav2 NavigateToPose (si carte + Nav2 actifs) |
| CaptureCamera | OUI | front ou claw |
| AnalyzeScene | OUI | Analyse environnement pendant navigation |
| RecognizeObject | OUI | Detection obstacles visuels |
| RecognizeQRCode | OUI | Points de navigation par QR |
| GetBatteryVoltage | OUI | Monitoring batterie |
| Beep | OUI | Signaux sonores |
| SetLamps | OUI | Signaux visuels |
| Speak | STUB | |
| Listen | STUB | |
| ControlServo | NON | Bras en pose anti-collision (1) |
| ControlArm | NON | Bras replie pendant navigation |
| ControlClaw | NON | Pince fermee pendant navigation |
| SetArmPose | OUI | Uniquement pose 1 (anti-collision) |

### Constraints
- Bras MUST etre en pose anti-collision (SetArmPose 1) avant de naviguer
- LiDAR safety REQUIRED (LIDAR_SAFETY_REQUIRED=true)
- Vitesse max: 0.06 m/s linear, 0.25 rad/s angular
- SLAM doit etre lance avant NavigateTo

### Sous-modes

#### 1a: NAVIGATION_MAPPING (SLAM actif, creation de carte)
- Cartographer tourne, cree la carte en temps reel
- NavigateTo NON disponible (pas de carte finale)
- SetVelocity + Stop pour deplacer le robot manuellement
- /map/live pour voir la carte en construction
- /maps/save pour sauvegarder la carte

#### 1b: NAVIGATION_AUTONOMOUS (Nav2 avec carte existante)
- Cartographer OFF, Nav2 ON avec carte sauvegardee
- NavigateTo disponible (envoie NavigateToPose goal)
- Nav2 planifie le chemin et evite les obstacles
- SetVelocity disponible en override manuel

#### 1c: NAVIGATION_3D (SLAM 3D avec Orbbec)
- Utilise la camera 3D Orbbec pour RTAB-Map ou Cartographer 3D
- Depth + RGB -> PointCloud2 -> costmap 3D
- Detection d'obstacles en 3D (meilleure que LiDAR 2D seul)

### Transitions sortantes
- -> STANDBY: commande "standby" ou timeout (pas de mouvement pendant 60s)
- -> MANIPULATION: commande "mode manipulation" (arret robot, repli bras)
- -> EVOLUTION: commande "mode evolution" (arret tout, mode dev)

---

## Mode 2: MANIPULATION

### Description
Mode de manipulation d'objets avec le bras 5-DOF et la pince. Utilise la
camera 3D Orbbec pour la perception de profondeur et la camera claw pour
la vue proche. Le robot reste immobile (roues arretees).

### Sous-systemes actifs

| Sous-systeme | Etat | Usage |
|-------------|------|-------|
| Driver node | INACTIF | Roues arretees (cmd_vel = 0) |
| LiDAR | INACTIF | Pas besoin d'evitement |
| Camera 3D Orbbec | ACTIF | Depth pour saisie d'objets |
| Camera front (video0) | ACTIF | Vue large de la scene |
| Camera claw (video2) | OPTIONNEL | Vue proche de la pince |
| YOLO | OPTIONNEL | Detection d'objets a saisir |
| SLAM | INACTIF | Pas de cartographie |
| Hardware service | ACTIF | Controle servos, bras, pince |

### Tools disponibles (14/17)

| Tool | Disponible | Notes |
|------|-----------|-------|
| SetVelocity | NON | Roues arretees en manipulation |
| Stop | OUI | Arret du bras (return to pose 1) |
| NavigateTo | NON | Pas de navigation |
| CaptureCamera | OUI | front + claw pour perception |
| AnalyzeScene | OUI | Analyser la scene pour planifier saisie |
| RecognizeObject | OUI | Identifier objets a saisir |
| RecognizeFace | OUI | (si interaction humain) |
| RecognizeQRCode | OUI | (si objets etiquetes QR) |
| ControlServo | OUI | Controle individuel servos 1-6 |
| ControlArm | OUI | Controle bras 5-DOF |
| ControlClaw | OUI | Ouverture/fermeture pince |
| SetArmPose | OUI | Poses predefinies + anti-collision |
| Beep | OUI | |
| SetLamps | OUI | |
| GetBatteryVoltage | OUI | |
| Speak | STUB | |
| Listen | STUB | |

### Constraints
- Roues MUST etre arretees (cmd_vel = 0) avant manipulation
- Bras DOIT etre sorti de pose anti-collision avant manipulation
- Pas de MoveIt2 (controle manuel par angles, pas de planification de trajectoire)
- Camera 3D fournit depth pour estimer la distance des objets

### Sous-modes

#### 2a: MANIPULATION_INSPECTION (observation sans contact)
- Bras en position d'observation (eleve, camera claw vers objet)
- CaptureCamera claw pour vue proche
- AnalyzeScene pour analyser
- Pas de contact avec l'objet

#### 2b: MANIPULATION_GRASP (saisie d'objet)
- Camera 3D pour estimer position 3D de l'objet
- ControlArm pour approcher
- ControlClaw open -> close pour saisir
- SetArmPose 1 pour replier apres saisie

#### 2c: MANIPULATION_PLACE (depot d'objet)
- ControlArm pour deplacer vers position cible
- ControlClaw open pour relacher
- SetArmPose 1 pour replier

### Transitions sortantes
- -> STANDBY: commande "standby" ou fin de tache
- -> NAVIGATION: commande "mode navigation" (SetArmPose 1, attendre, activer SLAM)
- -> EVOLUTION: commande "mode evolution"

---

## Mode 3: EVOLUTION

### Description
Mode de developpement et d'auto-amelioration. Le robot ne bouge pas.
Ce mode permet a l'agent LLM de modifier son propre code, ses skills,
sa base de connaissance, et de lancer des tests de non-regression.

### Sous-systemes actifs

| Sous-systeme | Etat | Usage |
|-------------|------|-------|
| Driver node | INACTIF | Robot immobile |
| LiDAR | INACTIF | |
| Camera 3D | INACTIF | |
| Cameras | INACTIF | |
| SLAM | INACTIF | |
| Hardware service | ACTIF | Monitoring batterie uniquement |
| Bridge C++ | ACTIF | API disponible pour tests |
| Tests | ACTIF | Script de non-regression |

### Tools disponibles (5/17)

| Tool | Disponible | Notes |
|------|-----------|-------|
| GetBatteryVoltage | OUI | Monitoring pendant le dev |
| Beep | OUI | Signal de debut/fin de modification |
| SetLamps | OUI | Indicator visuel (mode dev = bleu) |
| Stop | OUI | Safety |
| CaptureCamera | OUI | Pour verification visuelle si besoin |

### Tools NON disponibles en mode EVOLUTION
SetVelocity, NavigateTo, ControlServo, ControlArm, ControlClaw, SetArmPose,
AnalyzeScene, RecognizeFace, RecognizeObject, RecognizeQRCode, Speak, Listen

### Capacites specifiques au mode EVOLUTION
- Lecture/ecriture de fichiers (code, config, docs)
- Build colcon (recompilation)
- Execution des tests de non-regression
- Mise a jour de la knowledge base OKF
- Modification des skills Hermes
- Mise a jour du system prompt
- Git operations (commit, push)

### Indicator visuel
- LEDs en BLEU pendant le mode evolution
- Beep court au debut et a la fin d'une modification

### Transitions sortantes
- -> STANDBY: commande "standby" ( LEDs off, retour mode defaut)
- -> NAVIGATION: commande "mode navigation"
- -> MANIPULATION: commande "mode manipulation"

---

## Mode 4: STANDBY (par defaut)

### Description
Mode d'attente. Le robot est reveille mais inactif. Il attend des instructions
via le canal de messagerie (vocal, texte, API). Consomme un minimum de ressources.

### Sous-systemes actifs

| Sous-systeme | Etat | Usage |
|-------------|------|-------|
| Driver node | ACTIF | Pret a recevoir cmd_vel |
| LiDAR | INACTIF | Pas de SLAM, pas de safety |
| Camera 3D | INACTIF | |
| Cameras | INACTIF | |
| SLAM | INACTIF | |
| Hardware service | ACTIF | Monitoring batterie, pret a action |
| Joy teleop | ACTIF | Controle manuel possible |
| Bridge C++ | ACTIF | API disponible |

### Tools disponibles (8/17)

| Tool | Disponible | Notes |
|------|-----------|-------|
| Stop | OUI | Safety |
| GetBatteryVoltage | OUI | Monitoring |
| Beep | OUI | Signaux |
| SetLamps | OUI | Indicator d'etat |
| SetVelocity | OUI | Joy teleop override |
| Speak | STUB | |
| Listen | STUB | Ecoute vocale (quand implemente) |
| SetArmPose | OUI | Pose 1 (anti-collision) uniquement |

### Comportement
- LEDs: VERT (pret, en attente)
- Bras en pose anti-collision (1)
- Roues arretees (cmd_vel = 0)
- Watchdog actif (1.5s)
- Accepte les instructions vocales/texte pour changer de mode

### Transitions sortantes
- -> NAVIGATION: "mode navigation" ou "va a [position]"
- -> MANIPULATION: "mode manipulation" ou "prends [objet]"
- -> EVOLUTION: "mode evolution" ou "modifie [fichier]"

---

## Matrice de Transition

| From \ To | STANDBY | NAVIGATION | MANIPULATION | EVOLUTION |
|-----------|---------|------------|-------------|-----------|
| STANDBY   | -       | OK         | OK          | OK        |
| NAVIGATION| OK      | -          | OK (stop+repli) | OK   |
| MANIPULATION| OK    | OK (stop+anti-collision) | -     | OK        |
| EVOLUTION | OK      | OK         | OK          | -         |

### Pre-conditions de transition

| Transition | Pre-conditions |
|-----------|----------------|
| * -> NAVIGATION | cmd_vel=0, SetArmPose(1), LiDAR ON, SLAM start |
| * -> MANIPULATION | cmd_vel=0, SLAM OFF (si actif), LiDAR OFF |
| * -> EVOLUTION | cmd_vel=0, SLAM OFF, bras en pose 1, LEDs bleu |
| * -> STANDBY | cmd_vel=0, SLAM OFF, bras en pose 1, LEDs vert |

## Implementation

Le mode_manager sera implemente comme:
1. Un endpoint REST: GET /mode, POST /mode (change mode)
2. Un filtre sur les tools: POST /command verifie le mode avant d'executer
3. Des transitions automatiques avec pre-conditions
4. Indicator visuel via SetLamps

Fichier: /home/jetson/clawbot/ros2_llm_bridge_cpp/src/mode_manager.cpp