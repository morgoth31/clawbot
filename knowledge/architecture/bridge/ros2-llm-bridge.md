---
type: API Bridge
title: "ROS2 LLM Bridge -- API REST (port 8000)"
description: Serveur FastAPI qui expose les 17 tools du robot au format OpenAI/Anthropic function calling. Tourne en Docker.
status: stable
tags: [api, fastapi, ros2, bridge, docker]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:15:00Z
sources:
  - id: api-server-src
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/ros2_llm_bridge/api_server.py
    title: api_server.py
    author: human:jetson
    last_modified: 2026-02-28
  - id: docker-compose
    resource: file:///home/jetson/clawbot/docker-compose.yml
    title: docker-compose.yml
    author: human:jetson
    last_modified: 2026-03-02
  - id: bridge-readme
    resource: file:///home/jetson/clawbot/ros2_llm_bridge/README.md
    title: ros2_llm_bridge README
    author: human:jetson
    last_modified: 2026-03-06
---

# ROS2 LLM Bridge

## Role

Le bridge est la couche d'abstraction entre l'agent LLM et le hardware.
Il expose 17 tools robotiques via une API REST sur le port 8000, avec
des schemas au format OpenAI/Anthropic pour le function calling.

## Architecture Interne

```
POST /command (HTTP)
  -> api_server.py (FastAPI)
  -> action_handler.py (validation Pydantic + dispatch)
  -> bridge_node.py (noeud ROS2)
  -> HTTP -> hardware_service.py (port 8001)
  -> ROS2 topics -> driver_node -> serial -> hardware
```

## Fichiers Clés

| Fichier | Taille | Role |
|---------|--------|------|
| `api_server.py` | 236 lignes | Serveur FastAPI, endpoints /tools, /command, /health |
| `action_handler.py` | 199 lignes | Registre 17 tools, validation, dispatch |
| `bridge_node.py` | 399 lignes | Noeud ROS2, traduit tool calls en appels HTTP |
| `schemas.py` | 274 lignes | 17 modeles Pydantic |

## Endpoints REST (port 8000)

### GET /tools
Retourne les schemas des 17 tools. Formats: `openai` (default), `anthropic`, `raw`.

### POST /command
Execute un tool. Payload: `{"function": "SetVelocity", "arguments": {...}}`
Retourne: `{"result": "..."}`

### GET /health
Health check pour Docker. Retourne `{"status": "healthy"}` si ROS2 node actif.

## Securite

- **API Key**: opt-in via env var `API_KEY`. Header `X-API-Key` requis si configure.
- **Timeouts par tool**: 2s (Stop) a 60s (NavigateTo)
- **Validation**: tous les args sont valides par Pydantic avant execution

## Docker

```yaml
# docker-compose.yml
services:
  llm_bridge:
    build: ./ros2_llm_bridge
    network_mode: "host"
    environment:
      - ROS_DOMAIN_ID=28
      - HARDWARE_SERVICE_URL=http://localhost:8001
    volumes:
      - ./ros2_llm_bridge:/app
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
```

## Lifecycle ROS2

- `rclpy.init()` au startup (FastAPI lifespan)
- `MultiThreadedExecutor` (4 threads) dans un thread daemon
- `node.destroy_node()` + `rclpy.shutdown()` au shutdown

## Status

**Production**. ~95% feature complete. Le bridge est la couche stable qui ne
changera pas lors du remplacement d'OpenClaw -- seul le consommateur de l'API change.