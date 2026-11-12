---
type: LLM Agent
title: "OpenClaw -- Agent LLM Multi-Canal"
description: Agent IA personnel qui recevait les commandes en langage naturel et dispatchait les tool calls vers le ros2_llm_bridge.
status: deprecated
tags: [llm, agent, openclaw, deprecated]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:15:00Z
sources:
  - id: openclaw-package
    resource: file:///home/jetson/.npm-global/lib/node_modules/openclaw/package.json
    title: OpenClaw package.json
    author: openclaw/openclaw
    last_modified: 2026-04-16
  - id: openclaw-config
    resource: file:///home/jetson/.openclaw/agents/main/agent/models.json
    title: OpenClaw models.json
    author: human:jetson
    last_modified: 2026-04-16
  - id: openclaw-readme
    resource: file:///home/jetson/.npm-global/lib/node_modules/openclaw/README.md
    title: OpenClaw README
    author: openclaw/openclaw
    last_modified: 2026-04-14
---

# OpenClaw -- Agent LLM Multi-Canal

## Role dans le Systeme

OpenClaw (v2026.4.14) etait le "cerveau" du robot -- l'agent LLM au sommet de la stack.
Il recevait les messages utilisateur en langage naturel via des canaux de messagerie
(WhatsApp, Telegram, Slack, Discord, etc.), appliquait le raisonnement LLM pour choisir
quel tool appeler, puis envoyait les requetes au [ros2_llm_bridge](/architecture/bridge/ros2-llm-bridge.md).

## Installation

- **Chemin**: `/home/jetson/.npm-global/lib/node_modules/openclaw/`
- **Version**: 2026.4.14 (commit 323493f)
- **Binaire**: `/home/jetson/.npm-global/bin/openclaw`
- **Config**: `/home/jetson/.openclaw/agents/main/agent/`
- **Workspace**: `/home/jetson/.openclaw/workspace/` (reference dans hardware_service)

## Models Configures

### Provider: Codex (OpenAI ChatGPT backend)
- gpt-5.4 (reasoning, text+image, 272k context)
- gpt-5.4-mini (reasoning, text+image, 272k context)
- gpt-5.2 (reasoning, text+image, 272k context)
- API: `openai-codex-responses`
- Base URL: `https://chatgpt.com/backend-api/v1`

### Provider: Ollama (local)
- gemma4 (text+image, 128k context)
- gemma4:latest (text+image, 131k context)
- qwen3.5:0.8b (text+image, 262k context)
- qwen3.5:9b (text+image, 262k context)
- tinyllama:1.1b (text only, 2k context)
- API: `ollama`
- Base URL: `http://127.0.0.1:11434/v1`

## Auth Profiles
- `ollama:default`: type api_key, provider ollama, key "ollama-local"

## Skills (55+)
OpenClaw embarque 55+ skills dont:
- `clawhub` -- CLI pour installer/publier des skills depuis clawhub.com
- `coding-agent` -- Delegation de code
- `discord`, `slack`, `telegram` -- Canaux de messagerie
- `himalaya` -- Email terminal
- `obsidian` -- Notes
- `notion` -- Notion API
- `github`, `gh-issues` -- GitHub
- `openai-whisper` -- STT
- `peekaboo` -- Camera capture
- `songsee` -- Audio analysis
- `weather`, `gifgrep`, `summarize` -- Utilitaires

## Flux de Commande

```
Utilisateur (texte/voix)
  -> OpenClaw recoit le message sur un canal
  -> OpenClaw LLM raisonne, choisit un tool
  -> POST http://localhost:8000/command
     {"function": "SetVelocity", "arguments": {"linear_x": 0.05, ...}}
  -> [ros2_llm_bridge] traite et execute
  -> OpenClaw recoit le resultat
  -> OpenClaw repond a l'utilisateur
```

## Points d'Integration avec le Robot

1. **Tool calling**: OpenClaw decouvrait les tools via `GET /tools` du bridge
2. **Format supporte**: openai, anthropic, raw (Pydantic JSON Schema)
3. **Workspace**: `/home/jetson/.openclaw/workspace/` -- ou les images capturees etaient sauvegardees
4. **env_file**: `/home/jetson/clawbot/.env` (vide, garde pour docker-compose)

## Raison du Remplacement

OpenClaw est un assistant personnel multi-canal genérique -- il n'est pas specialise
pour le controle robotique. Le remplacer par un agent dedie permet:
- Un system prompt specialise robotique
- Une integration native avec Hermes Agent (deja present sur la machine)
- La suppression de la dependance npm/Node.js
- Un controle direct sur le cycle de raisonnement
- La conservation du bridge ROS2 intact (c'est la couche stable)

Voir [Rapport de Remplacement](/rapport-remplacement-openclaw.md) pour le plan detaille.