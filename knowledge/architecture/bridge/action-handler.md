---
type: Component
title: "Action Handler -- Registre des 17 Tools"
description: Mappe les requetes HTTP aux methodes du BridgeNode. Valide les arguments avec Pydantic et supporte les formats OpenAI/Anthropic/raw.
status: stable
tags: [api, tools, pydantic, function-calling]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:15:00Z
sources:
  - id: action-handler-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/ros2_llm_bridge/action_handler.py
    title: action_handler.py
    author: human:jetson
    last_modified: 2026-02-28
---

# Action Handler

## Role

Le ActionHandler est le registre central qui mappe chaque nom de tool a:
1. Un schema Pydantic (pour la validation)
2. Une methode handler async du BridgeNode
3. Un timeout (en secondes)

## Registry des 17 Tools

| Tool | Schema | Timeout | Category |
|------|--------|---------|----------|
| SetVelocity | SetVelocity | 5s | Motion |
| Stop | Stop | 2s | Motion |
| Speak | Speak | 15s | Motion |
| NavigateTo | NavigateTo | 60s | Navigation |
| CaptureCamera | CaptureCamera | 10s | Vision |
| AnalyzeScene | AnalyzeScene | 15s | Vision |
| RecognizeFace | RecognizeFace | 10s | Vision |
| RecognizeObject | RecognizeObject | 10s | Vision |
| RecognizeQRCode | RecognizeQRCode | 10s | Vision |
| Listen | Listen | 30s | Audio |
| ControlServo | ControlServo | 5s | Arm |
| ControlArm | ControlArm | 10s | Arm |
| ControlClaw | ControlClaw | 5s | Arm |
| SetArmPose | SetArmPose | 10s | Arm |
| Beep | Beep | 5s | Peripherals |
| SetLamps | SetLamps | 2s | Peripherals |
| GetBatteryVoltage | GetBatteryVoltage | 3s | Peripherals |

## Formats de Schema

### OpenAI (default)
```json
{"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
```

### Anthropic
```json
{"name": "...", "description": "...", "input_schema": {...}}
```

### Raw
JSON Schema brut de Pydantic.

## Flow d'Execution

1. `execute_tool(func_name, args)` est appele
2. Genere un `correlation_id` (UUID) pour le tracing
3. Valide args avec `schema_cls(**args)` (Pydantic ValidationError -> ValueError)
4. Appelle `handler(cid, validated_model)`
5. Retourne le resultat string

## Correlation IDs

Chaque execution recoit un UUID unique qui est logge a chaque etape:
- `[CID: xxx] Executing 'SetVelocity' with args: {...}`
- `[CID: xxx] Result: Velocity set: vx=0.05...`

Ce systeme permet de tracer une commande de l'API jusqu'au hardware.