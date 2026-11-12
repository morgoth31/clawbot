---
type: Schema Reference
title: "Schemas Pydantic -- 17 Modeles de Tools"
description: Contrats d'interface LLM pour le function calling. Chaque modele definit les parametres, limites et descriptions pour un tool robotique.
status: stable
tags: [pydantic, schemas, llm, function-calling]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:15:00Z
sources:
  - id: schemas-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/ros2_llm_bridge/schemas.py
    title: schemas.py
    author: human:jetson
    last_modified: 2026-02-28
---

# Schemas Pydantic (17 Tools)

## Motion

### SetVelocity
- `linear_x`: float, -0.06 a 0.06 m/s (forward+)
- `linear_y`: float, -0.06 a 0.06 m/s (left+, Mecanum)
- `angular_z`: float, -0.25 a 0.25 rad/s (CCW+)
- **Hard limits** enforcees par hardware_service

### Stop
- Aucun parametre. Arret immediat.

### Speak
- `text`: str (phrase a synthetiser)
- **Status**: stub, TTS non cable

## Navigation

### NavigateTo
- `target_x`: float (metres, map frame)
- `target_y`: float (metres, map frame)
- **Status**: stub, Nav2 non cable

## Vision

### CaptureCamera
- `camera`: Literal["front", "claw"] (default: "front")
- front = /dev/video0, claw = /dev/video2

### AnalyzeScene / RecognizeFace / RecognizeObject / RecognizeQRCode
- Aucun parametre. Captures la camera front et retourne image base64.
- L'agent LLM doit ensuite utiliser un tool d'analyse d'image sur le saved_path.

## Audio

### Listen
- Aucun parametre. STT non cable (stub).

## Arm & Claw

### ControlServo
- `servo_id`: int 1-6
- `angle`: float 0-180 degres

Servo map:
1. Base rotation (0-180, centre=90)
2. Shoulder lift
3. Elbow reach
4. Wrist tilt (pitch)
5. Wrist rotate (roll)
6. Claw open/close (0=open, 180=closed)

### ControlArm
- `joints_array`: List[float], exactement 5 valeurs [base, shoulder, elbow, wrist-tilt, wrist-rotate]
- Chaque valeur: 0-180 degres

### ControlClaw
- `state`: Literal["open", "close"]
- open = 0 degres, close = 180 degres

### SetArmPose
- `pose_id`: int 1-3
  1. Anti-collision (plie, safe pour navigation)
  2. Dance (bras tendu horizontal)
  3. Line-tracking (bras bas, camera vers l'avant/bas)

## Peripherals

### Beep
- `delay_ms`: int, 1-5000 ms

### SetLamps
- `r`: int 0-255 (rouge)
- `g`: int 0-255 (vert)
- `b`: int 0-255 (bleu)

### GetBatteryVoltage
- Aucun parametre. Retourne voltage + % charge (3S LiPo: 9.6V-12.6V).