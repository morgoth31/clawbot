---
okf_version: 0.2
---

# Clawbot Knowledge Base

Base de connaissance du robot Clawbot (Yahboom X3 Plus + Jetson).
Documente l'architecture logicielle, le hardware, les services, les problemes connus,
et le plan de remplacement d'OpenClaw.

## Architecture

- [OpenClaw -- Agent LLM](architecture/llm-agent/openclaw.md) -- Couche IA: raisonnement, function calling, multi-canal
- [ROS2 LLM Bridge](architecture/bridge/ros2-llm-bridge.md) -- API REST (port 8000): expose 17 tools au format OpenAI/Anthropic
- [Action Handler](architecture/bridge/action-handler.md) -- Registre des tools, validation Pydantic, dispatch
- [Bridge Node](architecture/bridge/bridge-node.md) -- Noeud ROS2: traduit tool calls en topics/services ROS2
- [Schemas](architecture/bridge/schemas.md) -- 17 modeles Pydantic (contrats d'interface LLM)
- [Hardware Service](architecture/hardware-service/hardware-service.md) -- API REST (port 8001): controle hardware direct
- [Hardware Service -- Endpoints](architecture/hardware-service/endpoints.md) -- Catalogue des 30+ endpoints REST
- [Nervous System](architecture/hardware-service/nervous-system.md) -- Philosophie de design: 2 systemes (reflexes + analyse)

## Hardware

- [Robot Physique](hardware/robot.md) -- Yahboom X3 Plus, roues Mecanum, bras 5-DOF + pince
- [Capteurs](hardware/sensors.md) -- LiDAR, IMU, cameras, batterie
- [URDF](hardware/urdf.md) -- Modele URDF: 9 links, 8 joints

## Infrastructure

- [Services Systemd](infrastructure/systemd-services.md) -- 6 services auto-start
- [Docker Compose](infrastructure/docker-compose.md) -- Orchestration bridge + monitoring
- [ROS2 Configuration](infrastructure/ros2-config.md) -- Domain 28, FastDDS, topics

## Problemes Connus

- [Conflit Port Serie](issues/serial-conflict.md) -- hardware_service vs driver_node sur /dev/myserial
- [Odometrie Cassee](issues/odometry-broken.md) -- /odom toujours 0,0,0
- [Stubs Non Implementes](issues/stubs.md) -- NavigateTo, Speak, Listen
- [MoveIt2 Manquant](issues/moveit2.md) -- Planification bras 5-DOF non cablee

## Fonctionnalites et Tests

- [Liste des Fonctionnalites](features-list.md) -- 43 fonctionnalites (17 tools bridge + 23 endpoints HW + 3 meta)
- [Procedure de Test](test-procedure.md) -- Script de non-regression + resultats

## Rapport de Modification

- [Rapport Remplacement OpenClaw](rapport-remplacement-openclaw.md) -- Analyse + plan de modification