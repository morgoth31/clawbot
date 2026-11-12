---
type: Test Report
title: "Procedure de Test de Non-Regression -- Clawbot"
description: Procedure complete de test des 43 fonctionnalites du bridge et hardware_service. Inclut les resultats de la premiere execution.
status: stable
tags: [testing, regression, validation, procedure]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:25:00Z
sources:
  - id: test-script
    resource: file:///home/jetson/clawbot/tests/test_regression.py
    title: test_regression.py
  - id: features-list
    resource: file:///home/jetson/clawbot/knowledge/features-list.md
    title: features-list.md
---

# Procedure de Test de Non-Regression

## Script de Test

**Fichier**: `/home/jetson/clawbot/tests/test_regression.py`
**Resultats JSON**: `/home/jetson/clawbot/tests/test_results_*.json`

## Usage

```bash
# Test complet (mouvement + cameras + hardware)
python3 /home/jetson/clawbot/tests/test_regression.py

# Test sans bouger le robot (cameras + arm + peripherals)
python3 /home/jetson/clawbot/tests/test_regression.py --skip-motion

# Test bridge uniquement (pas de hardware direct)
python3 /home/jetson/clawbot/tests/test_regression.py --skip-hardware

# Test sans cameras
python3 /home/jetson/clawbot/tests/test_regression.py --skip-camera

# Specifier un fichier de sortie
python3 /home/jetson/clawbot/tests/test_regression.py --output /tmp/my_report.json
```

## Categories de Test (41 tests au total)

### 1. Bridge Meta Endpoints (7 tests)
- M1: GET /health (bridge alive)
- M2-openai: GET /tools?format=openai (17 tools)
- M2-anthropic: GET /tools?format=anthropic (17 tools)
- M2-raw: GET /tools?format=raw (17 tools)
- M2-names: Verification des 17 noms de tools
- M3-err: POST /command tool inconnu -> 400
- M3-args: POST /command args invalides -> 400

### 2. Hardware Service Meta (4 tests)
- H1: GET /health (ROS2 node + cameras config)
- H2: GET /system/status (services + nodes + topics)
- H3: GET /telemetry (IMU + velocity + servos + battery)
- H12: GET /battery (voltage + percentage)

### 3. Motion (4 tests, --skip-motion pour desactiver)
- T1: SetVelocity (forward 0.03 m/s via bridge)
- T1b: SetVelocity clamping (1.0 -> 0.06 via HW)
- T2: Stop (via bridge)
- H5: POST /motion/stop (via HW)

### 4. Stubs (3 tests)
- T3: Speak (retour stub attendu)
- T4: NavigateTo (retour stub attendu)
- T10: Listen (retour stub attendu)

### 5. Vision (8 tests, --skip-camera pour desactiver)
- T5: CaptureCamera (front, via bridge)
- T5b: CaptureCamera (claw, via bridge)
- T6: AnalyzeScene (via bridge)
- T7: RecognizeFace (via bridge)
- T8: RecognizeObject (via bridge)
- T9: RecognizeQRCode (via bridge)
- H21: GET /capture (front, via HW)
- H22: GET /yolo/frame (via HW)
- H23: GET /yolo/status (via HW)

### 6. Arm & Claw (4 tests)
- T11: ControlServo (servo 1 -> 90)
- T12: ControlArm ([90,90,90,90,90])
- T13: ControlClaw (open + close + open)
- T14: SetArmPose (1=Anti-collision)

### 7. Peripherals (3 tests)
- T15: Beep (100ms)
- T16: SetLamps (R, G, B, off)
- T17: GetBatteryVoltage (via bridge)

### 8. SLAM & Maps (3 tests)
- H15: GET /slam/status
- H17: GET /maps
- H16: GET /map/live (SKIP si SLAM non lance)

### 9. End-to-End: Instructions Haut Niveau (4 tests)
- E2E-1: "quelle est ta batterie" -> GetBatteryVoltage
- E2E-2: "telemetrie complete" -> GET /telemetry
- E2E-3: "position anti-collision puis arrete" -> SetArmPose + Stop
- E2E-4: "signal lumineux rouge puis eteint" -> SetLamps x2

## Resultats de la Premiere Execution (2026-08-10)

### Run 1: --skip-motion --skip-camera (bridge + arm + peripherals)

```
RESULTATS: 41 tests
PASS: 30  FAIL: 0  SKIP: 11  WARN: 0
STATUT GLOBAL: SUCCES
```

### Run 2: --skip-motion (avec cameras, apres fix workspace)

```
RESULTATS: 41 tests
PASS: 36  FAIL: 0  SKIP: 4  WARN: 1
STATUT GLOBAL: SUCCES
```

### Detail des SKIP/WARN

| Test | Status | Raison |
|------|--------|--------|
| T1, T1b | SKIP | --skip-motion (robot sur support, pas sur sol) |
| T5b (camera claw) | WARN | /dev/video2 n'existe pas physiquement (camera claw deconnectee) |
| H16 (map/live) | SKIP | SLAM non lance (normal) |
| H22 (yolo/frame) | SKIP | Service yolo-detector inactif (normal, manuel) |

### Bug decouvert et corrige

**Bug**: `FileNotFoundError` sur `/home/jetson/.openclaw/workspace/camera_front.jpg`
**Cause**: Le repertoire workspace d'OpenClaw n'existait pas
**Fix**: `mkdir -p /home/jetson/.openclaw/workspace`
**Note**: Ce bug confirme le point de modification #3 du rapport: WORKSPACE_PATH
doit etre migre vers `/home/jetson/clawbot/workspace/` lors du remplacement d'OpenClaw

## Procedure de Test Apres Modification

Quand une modification est apportee au systeme:

1. **Avant modification**: Lancer `python3 tests/test_regression.py --skip-motion`
   et sauvegarder le rapport JSON comme baseline

2. **Apres modification**: Relancer le meme script

3. **Comparer**: Les deux rapports JSON doivent avoir le meme nombre de PASS
   (ou plus). Aucun nouveau FAIL ne doit apparaitre.

4. **Si un test passe de PASS a FAIL**: Regression identifiee. Corriger avant
   de continuer.

5. **Si un test passe de SKIP/WARN a PASS**: Amelioration (bon signe).

6. **Si un nouveau test est ajoute**: L'ajouter au script et documenter dans
   features-list.md.