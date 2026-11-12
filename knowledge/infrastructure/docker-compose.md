---
type: Infrastructure
title: "Docker Compose -- Bridge + Monitoring"
description: Orchestration Docker du ros2_llm_bridge et du monitoring dashboard.
status: stable
tags: [docker, infrastructure, compose]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:30:00Z
sources:
  - id: docker-compose-src
    resource: file:///home/jetson/clawbot/docker-compose.yml
    title: docker-compose.yml
    author: human:jetson
    last_modified: 2026-03-02
---

# Docker Compose

## Services

### llm_bridge
- **Build**: ./ros2_llm_bridge
- **Network**: host (pour acces ROS2 DDS + hardware_service)
- **Ports**: 8000 (API), expose healthcheck
- **Env**:
  - ROS_DOMAIN_ID=28
  - HARDWARE_SERVICE_URL=http://localhost:8001
  - HARDWARE_SERVICE_TIMEOUT=10.0
  - FASTRTPS_DEFAULT_PROFILES_FILE=/app/fastdds_profile.xml
- **Volumes**:
  - ./ros2_llm_bridge:/app (hot reload)
  - ./fastdds_profile.xml:/app/fastdds_profile.xml:ro
- **env_file**: .env (vide, garde pour compat)
- **IPC**: host (pour DDS shared memory)
- **Healthcheck**: curl http://localhost:8000/health (30s interval, 10s timeout)
- **Restart**: unless-stopped

### clawbot_monitoring
- **Build**: ./clawbot_monitoring
- **Network**: host
- **Env**:
  - LLM_BRIDGE_URL=http://localhost:8000
  - HARDWARE_SERVICE_URL=http://localhost:8001
- **Volumes**: fastdds_profile.xml:ro
- **Restart**: unless-stopped
- **Port**: 5000 (web dashboard)

## Network Mode: host

Les deux services utilisent `network_mode: "host"` car:
1. ROS2 DDS utilise multicast/broadcast qui ne traverse pas les bridges Docker
2. Le bridge doit atteindre localhost:8001 (hardware_service sur le host)
3. IPC=host pour shared memory DDS