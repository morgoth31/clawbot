---
type: Design Document
title: "Nervous System -- Philosophie de Design"
description: Architecture bio-inspiree en 2 systemes: reflexes autonomes (rapide) et analyse cognitive (lent).
status: stable
tags: [design, architecture, nervous-system]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:20:00Z
sources:
  - id: nervous-sys-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/nervous_system.md
    title: nervous_system.md
    author: human:jetson
    last_modified: 2026-02-28
---

# Nervous System -- Philosophie de Design

## Systeme 1: Reflexes Autonomes (Rapide)

Operations qui doivent fonctionner sans LLM, sans reseau, sans latence cognitive.

### Reconnaissance Vocale
- Detection du nom "Clawbot"
- Commande vocale "stop" -> arret immediat
- Commande vocale "clawbot" -> mode ecoute d'instructions

### Arret d'Urgence
- Analyse LiDAR en temps reel
- Detection d'obstacle -> stop automatique
- Cartographie SLAM pour contexte spatial

## Systeme 2: Analyse Cognitive (Lent)

Operations qui requirent du raisonnement, du LLM, de la vision.

### Vision
- Reconnaissance de visages
- Reconnaissance d'objets
- Decodage de QR codes
- Analyse de scene complete

### Audio
- Reconnaissance vocale (STT)
- Synthese vocale (TTS)
- LLM de discussion

## Roadmap (Stories)

1. **Noeuds Maps**: SLAM, navigation autonome, localisation
2. **Noeuds Vision**: visages, objets, QR codes, scene
3. **Noeuds Son**: STT, TTS, LLM discussion
4. **Noeuds Controle**: roues, bras, pince
5. **Noeuds Integration**: communication inter-noeuds, gestion d'erreurs

## Status Actuel

| Story | Status |
|-------|--------|
| Maps (SLAM) | Operationnel (Cartographer LiDAR) |
| Navigation | Stub (Nav2 non cable) |
| Vision (YOLO) | Operationnel (yolo_node) |
| Vision (LLM) | Partiel (capture + LLM analysis) |
| Son (STT/TTS) | Stubs non implantes |
| Controle roues | Operationnel |
| Controle bras | Operationnel (sans MoveIt2) |
| Integration | Partiel (bridge + hardware_service) |