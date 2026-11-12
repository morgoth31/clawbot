---
type: Known Issue
title: "Stubs Non Implementes -- NavigateTo, Speak, Listen"
description: Trois tools du bridge sont des stubs qui retournent des reponses factices sans action reelle.
status: draft
tags: [todo, stubs, nav2, tts, stt]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:35:00Z
sources:
  - id: bridge-node-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/ros2_llm_bridge/bridge_node.py
    title: bridge_node.py
    author: human:jetson
    last_modified: 2026-02-28
---

# Stubs Non Implementes

## NavigateTo
- **Status**: stub
- **Ce qui manque**: Nav2 NavigateToPose action client
- **Dependencies**: Nav2 actif, carte SLAM, localisation (AMCL)
- **Code actuel**: retourne `{"status": "stub", "message": "Nav2 not wired yet"}`

## Speak (TTS)
- **Status**: stub
- **Ce qui manque**: service TTS ROS2
- **Options**: pyttsx3 (offline), Google TTS, OpenAI TTS, sherpa-onnx-tts
- **Code actuel**: retourne `Speak acknowledged: "text"` sans synthese

## Listen (STT)
- **Status**: stub
- **Ce qui manque**: service STT ROS2
- **Options**: Whisper (openai-whisper skill dans OpenClaw), vosk, sherpa-onnx
- **Code actuel**: retourne `{"status": "stub", "message": "STT not wired yet"}`

## Priorite pour le Remplacement d'OpenClaw
Ces stubs sont independants du remplacement d'OpenClaw. Ils restent des stubs
quel que soit l'agent LLM utilise. Cependant, un agent dedie pourrait les
implementer plus facilement car il aurait un controle direct sur le cycle de vie.