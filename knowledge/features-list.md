---
type: Feature List
title: "Liste Complete des Fonctionnalites du Bridge et Hardware Service"
description: Inventaire exhaustuel des endpoints, tools, et capacites du systeme Clawbot. Source de verite pour les tests de non-regression.
status: stable
tags: [features, testing, reference]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-11T00:00:00Z
sources:
  - id: api-server-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/ros2_llm_bridge/api_server.py
    title: api_server.py
  - id: hw-service-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/hardware_service.py
    title: hardware_service.py
  - id: action-handler-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/ros2_llm_bridge/action_handler.py
    title: action_handler.py
---

# Liste Complete des Fonctionnalites

## COUCHE 1: Bridge API (port 8000) -- 3 endpoints meta + 17 tools

### Meta Endpoints

| ID | Endpoint | Methode | Description |
|----|----------|---------|-------------|
| M1 | /health | GET | Health check (ROS2 node alive) |
| M2 | /tools | GET | Liste les 17 tools (format openai/anthropic/raw) |
| M3 | /command | POST | Execute un tool par nom + arguments |

### Tool 1: SetVelocity
- **Bridge**: POST /command {"function":"SetVelocity","arguments":{"linear_x":0.05,"linear_y":0,"angular_z":0}}
- **HW**: POST /motion {"linear_x":0.05,"linear_y":0,"angular_z":0}
- **Limits**: linear ±0.06 m/s, angular ±0.25 rad/s
- **Safety**: clamping + LiDAR obstacle check (si active)
- **Watchdog**: auto-stop apres 1.5s sans commande

### Tool 2: Stop
- **Bridge**: POST /command {"function":"Stop","arguments":{}}
- **HW**: POST /motion/stop
- **Fallback**: si HW injoignable, publish Twist() sur /cmd_vel directement

### Tool 3: Speak
- **Bridge**: POST /command {"function":"Speak","arguments":{"text":"hello"}}
- **Status**: STUB -- retourne ack sans TTS reel

### Tool 4: NavigateTo
- **Bridge**: POST /command {"function":"NavigateTo","arguments":{"target_x":1,"target_y":2}}
- **Status**: STUB -- Nav2 non cable

### Tool 5: CaptureCamera
- **Bridge**: POST /command {"function":"CaptureCamera","arguments":{"camera":"front"}}
- **HW**: GET /capture?camera=front&save=true
- **Retour**: base64 JPEG + saved_path
- **Cameras**: front (/dev/video0), claw (/dev/video2)

### Tool 6: AnalyzeScene
- **Bridge**: POST /command {"function":"AnalyzeScene","arguments":{}}
- **HW**: capture front camera
- **Retour**: image base64 + instruction pour LLM

### Tool 7: RecognizeFace
- **Bridge**: POST /command {"function":"RecognizeFace","arguments":{}}
- **HW**: capture front camera
- **Retour**: image base64 + instruction

### Tool 8: RecognizeObject
- **Bridge**: POST /command {"function":"RecognizeObject","arguments":{}}
- **HW**: capture front camera
- **Retour**: image base64 + instruction

### Tool 9: RecognizeQRCode
- **Bridge**: POST /command {"function":"RecognizeQRCode","arguments":{}}
- **HW**: capture front camera
- **Retour**: image base64 + instruction

### Tool 10: Listen
- **Bridge**: POST /command {"function":"Listen","arguments":{}}
- **Status**: STUB -- STT non cable

### Tool 11: ControlServo
- **Bridge**: POST /command {"function":"ControlServo","arguments":{"servo_id":1,"angle":90}}
- **HW**: POST /servo {"servo_id":1,"angle":90}
- **Range**: servo_id 1-6, angle 0-180

### Tool 12: ControlArm
- **Bridge**: POST /command {"function":"ControlArm","arguments":{"joints_array":[90,90,90,90,90]}}
- **HW**: POST /arm {"joints":[90,90,90,90,90]}
- **Format**: 5 angles [base, shoulder, elbow, wrist-tilt, wrist-rotate]
- **Timing**: 60ms entre chaque servo

### Tool 13: ControlClaw
- **Bridge**: POST /command {"function":"ControlClaw","arguments":{"state":"open"}}
- **HW**: POST /claw {"state":"open"}
- **Mapping**: open=0 degres, close=180 degres (servo 6)

### Tool 14: SetArmPose
- **Bridge**: POST /command {"function":"SetArmPose","arguments":{"pose_id":1}}
- **HW**: POST /arm/pose/1
- **Poses**: 1=Anti-collision [90,130,10,60,90], 2=Dance [90,90,90,90,90], 3=Line-tracking [90,160,30,90,90]

### Tool 15: Beep
- **Bridge**: POST /command {"function":"Beep","arguments":{"delay_ms":200}}
- **HW**: POST /beep?delay_ms=200
- **Range**: 1-5000 ms

### Tool 16: SetLamps
- **Bridge**: POST /command {"function":"SetLamps","arguments":{"r":255,"g":0,"b":0}}
- **HW**: POST /lamps {"r":255,"g":0,"b":0}
- **Encoding**: RGB encode en Int32 (0xRRGGBB)

### Tool 17: GetBatteryVoltage
- **Bridge**: POST /command {"function":"GetBatteryVoltage","arguments":{}}
- **HW**: GET /battery
- **Retour**: voltage (V) + percentage (3S LiPo: 9.6V-12.6V)

## COUCHE 2: Hardware Service (port 8001) -- 23 endpoints + 1 YOLO

### Health & System

| ID | Endpoint | Methode | Description |
|----|----------|---------|-------------|
| H1 | /health | GET | Status ROS2 node + cameras config |
| H2 | /system/status | GET | Services systemd + docker + nodes ROS2 + topics + LiDAR + battery |
| H3 | /telemetry | GET | IMU + velocity + servos + battery (temps reel) |

### Motion

| ID | Endpoint | Methode | Description |
|----|----------|---------|-------------|
| H4 | /motion | POST | Set velocity (linear_x, linear_y, angular_z) + safety |
| H5 | /motion/stop | POST | Arret immediat (Twist zero) |

### Servos & Arm

| ID | Endpoint | Methode | Description |
|----|----------|---------|-------------|
| H6 | /servo | POST | Controle 1 servo (id 1-6, angle 0-180) |
| H7 | /arm | POST | Controle 5 servos bras (joints[5]) |
| H8 | /claw | POST | Open/close pince (servo 6) |
| H9 | /arm/pose/{id} | POST | Pose predefinie (1-3) |

### Peripherals

| ID | Endpoint | Methode | Description |
|----|----------|---------|-------------|
| H10 | /beep | POST | Buzzer (delay_ms 1-5000) |
| H11 | /lamps | POST | LEDs RGB (r,g,b 0-255) |
| H12 | /battery | GET | Voltage + percentage |

### SLAM & Maps

| ID | Endpoint | Methode | Description |
|----|----------|---------|-------------|
| H13 | /slam/start | POST | Lance Cartographer (subprocess) |
| H14 | /slam/stop | POST | Arrete SLAM (kill process group) |
| H15 | /slam/status | GET | SLAM actif ou non |
| H16 | /map/live | GET | Carte SLAM actuelle (base64 PNG) |
| H17 | /maps | GET | Liste cartes sauvegardees |
| H18 | /maps/save | POST | Sauvegarde carte (map_saver_cli) |
| H19 | /maps/{name}/image | GET | Image carte sauvegardee (base64 PNG) |
| H20 | /maps/{name} | DELETE | Supprime carte |

### Vision

| ID | Endpoint | Methode | Description |
|----|----------|---------|-------------|
| H21 | /capture | GET | Capture camera (front/claw, save option) |
| H22 | /yolo/frame | GET | Frame YOLO annotee (base64 + detections) |
| H23 | /yolo/status | GET | Etat service YOLO + dernier frame |

## RESUME

- **Bridge C++ (port 8000)**: 3 meta endpoints + 18 tools (dont 3 stubs: Speak, NavigateTo, Listen + DetectObjects YOLO)
- **Hardware Service (port 8001)**: 23 endpoints
- **YOLO Service (port 8003)**: 4 endpoints (/health, /model, /detect, /detect_raw)
- **Total**: 48 fonctionnalites testables
- **Stubs connus**: Speak, NavigateTo, Listen (retournent reponse factice)
- **Dependances optionnelles**: SLAM (doit etre lance), YOLO (service systemd auto-start)