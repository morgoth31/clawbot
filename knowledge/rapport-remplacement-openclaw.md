---
type: Modification Report
title: "Rapport de Modification -- Remplacement d'OpenClaw"
description: Analyse detaillee des modifications necessaires pour remplacer OpenClaw par un agent dedie. Points cles, impacts, et plan d'action.
status: draft
tags: [modification, openclaw, replacement, hermes, architecture]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:40:00Z
sources:
  - id: openclaw-doc
    resource: /architecture/llm-agent/openclaw.md
    title: OpenClaw documentation
  - id: bridge-doc
    resource: /architecture/bridge/ros2-llm-bridge.md
    title: ROS2 LLM Bridge documentation
  - id: hw-service-doc
    resource: /architecture/hardware-service/hardware-service.md
    title: Hardware Service documentation
---

# Rapport de Modification -- Remplacement d'OpenClaw

## 1. Contexte

OpenClaw (v2026.4.14) est un assistant IA personnel multi-canal installe via npm.
Il servait de "cerveau" au robot Clawbot: reception des messages, raisonnement LLM,
function calling vers le [ros2_llm_bridge](/architecture/bridge/ros2-llm-bridge.md)
(port 8000), et retour des resultats a l'utilisateur.

Le bridge ROS2 expose deja 17 tools au format OpenAI/Anthropic via `GET /tools`
et les execute via `POST /command`. Cette couche est stable et ne change pas.

Le remplacement d'OpenClaw consiste a remplacer la couche "cerveau LLM" sans
modifier le bridge, le hardware_service, ni les services systemd existants.

## 2. Ce que OpenClaw Faisait (a reproduire)

| Fonction | Detail |
|----------|--------|
| Reception messages | Multi-canal (Telegram, Discord, WhatsApp, etc.) |
| Raisonnement LLM | Models: gpt-5.4, gpt-5.2, gemma4, qwen3.5 (via codex/ollama) |
| Decouverte des tools | `GET http://localhost:8000/tools?format=openai` |
| Execution des tools | `POST http://localhost:8000/command {"function": "...", "arguments": {...}}` |
| Traitement images | Recois saved_path + base64, analyse avec vision LLM |
| Workspace | Sauvegarde images dans `/home/jetson/.openclaw/workspace/` |
| Skills | 55+ skills (himalaya, obsidian, github, whisper, etc.) |
| Auth | profiles ollama:default (api_key, ollama-local) |

## 3. Points de Modification Les Plus Importants

### 3.1. POINT CRITIQUE 1: Decouverte et Execution des Tools

**Status**: AUCUN CHANGEMENT necessaire dans le bridge.

Le bridge expose deja `/tools` (format openai/anthropic/raw) et `/command`.
Le nouvel agent doit:
1. Fetcher `GET http://localhost:8000/tools?format=openai` au demarrage
2. Injecter ces tools dans le system prompt du LLM
3. Quand le LLM retourne un function call, envoyer `POST /command`
4. Retourner le resultat au LLM pour le tour suivant

**Modification**: Aucune cote bridge. Cote nouvel agent: implementer le client HTTP.

### 3.2. POINT CRITIQUE 2: Configuration des Models

**Status**: MIGRATION necessaire.

OpenClaw utilisait deux providers:
- **Codex (OpenAI)**: gpt-5.4, gpt-5.4-mini, gpt-5.2 via `https://chatgpt.com/backend-api/v1`
- **Ollama (local)**: gemma4, qwen3.5:9b, qwen3.5:0.8b, tinyllama via `http://127.0.0.1:11434/v1`

Le nouvel agent doit reproduire cette configuration. Si Hermes Agent est utilise:
- Hermes supporte deja les providers ollama-cloud et openai-compatible
- Les models ollama locaux sont accessibles via `http://127.0.0.1:11434/v1`
- Les models codex necessitent une configuration custom du provider

**Modification**: Configurer les providers dans le nouvel agent. Fichier a modifier:
- Si Hermes: `~/.hermes/config.yaml` (providers, models)
- Si custom: fichier de config dedie

### 3.3. POINT CRITIQUE 3: Workspace et Sauvegarde Images

**Status**: MIGRATION necessaire.

OpenClaw utilisait `/home/jetson/.openclaw/workspace/` pour sauvegarder les images
capturees par le hardware_service (variable `WORKSPACE_PATH`).

Le hardware_service utilise deja cette variable d'environnement:
```
Environment=WORKSPACE_PATH=/home/jetson/.openclaw/workspace
```

**Modification**:
1. Changer `WORKSPACE_PATH` dans `ros2-hardware-service.service` vers un nouveau chemin
   (ex: `/home/jetson/clawbot/workspace/`)
2. Mettre a jour la variable dans le service systemd
3. Creer le nouveau repertoire
4. Redemarrer le service

### 3.4. POINT CRITIQUE 4: Canaux de Communication (Messagerie)

**Status**: MIGRATION PARTIELLE.

OpenClaw supportait 20+ canaux (WhatsApp, Telegram, Discord, Slack, etc.).
Le nouvel agent doit decider quels canaux garder.

Si Hermes Agent est utilise:
- Hermes supporte Telegram, Discord, WhatsApp, Signal, etc. via son gateway
- La configuration se fait via `hermes config` et les gateways
- Les skills Hermes incluent deja xurl (X/Twitter), himalaya (email), etc.

**Modification**:
1. Configurer les gateways Hermes pour les canaux desires
2. Transfert des credentials/tokens OpenClaw vers Hermes
3. Tester chaque canal

### 3.5. POINT CRITIQUE 5: System Prompt Robotique

**Status**: CREATION necessaire.

OpenClaw utilisait un system prompt generique d'assistant personnel.
Le nouvel agent doit avoir un system prompt specialise pour le controle robotique.

Le system prompt doit inclure:
- Identite: "Tu es Clawbot, un robot mobile Yahboom X3 Plus avec bras 5-DOF"
- Capacites: les 17 tools disponibles (auto-injectes via /tools)
- Safety: "NE JAMAIS depasser 0.06 m/s. Toujours Stop() apres un mouvement"
- Contexte spatial: "Tu as un LiDAR, 2 cameras, un IMU"
- Limitations: "NavigateTo, Speak et Listen sont des stubs non implementes"
- Personnalite: a definir par l'utilisateur

**Modification**: Creer un system prompt dedie. Si Hermes: configurer dans
le profil ou utiliser un skill dedie.

### 3.6. POINT IMPORTANT 6: Skills OpenClaw vs Hermes

**Status**: EVALUATION necessaire.

OpenClaw avait 55+ skills. Hermes en a ~60+. Tableau de correspondance:

| Skill OpenClaw | Equivalent Hermes | Status |
|----------------|-------------------|--------|
| coding-agent | claude-code, codex, opencode | Disponible |
| discord | gateway Discord | Disponible |
| telegram | gateway Telegram | Disponible |
| slack | gateway Slack | Disponible |
| himalaya | himalaya | Disponible (meme skill) |
| obsidian | obsidian | Disponible (meme skill) |
| notion | notion | Disponible (meme skill) |
| github | github-auth, github-* | Disponible (plus detaille) |
| openai-whisper | (non disponible) | A ajouter |
| peekaboo | computer-use | Equivalent |
| songsee | songsee | Disponible (meme skill) |
| weather | (non disponible) | A ajouter |
| gifgrep | gif-search | Disponible (meme skill) |
| summarize | (non disponible) | A ajouter |
| clawhub | (non applicable) | Non necessaire |

**Modification**: Identifier les skills manquants (whisper, weather, summarize)
et les ajouter a Hermes si necessaire.

### 3.7. POINT IMPORTANT 7: Traitement des Images (Vision)

**Status**: MIGRATION necessaire.

Quand un tool de vision (CaptureCamera, AnalyzeScene, etc.) est appele:
1. Le hardware_service capture une frame et retourne base64 + saved_path
2. Le bridge retourne ce JSON a l'agent
3. L'agent LLM doit analyser l'image (vision multimodale)

OpenClaw utilisait les models gpt-5.4/gpt-5.2 (text+image) ou gemma4:latest (text+image).

**Modification**: Le nouvel agent doit:
1. Supporter les images en entree (vision multimodale)
2. Pouvoir lire le saved_path ou decoder le base64
3. Si Hermes: utiliser l'outil vision_analyze ou computer_use pour analyser l'image
4. Si custom: integrer un model vision (gpt-4o, gemini, llava via ollama)

### 3.8. POINT IMPORTANT 8: Service Systemd

**Status**: MODIFICATION legere.

Si Hermes Agent est le rempla d'OpenClaw, il faut:
1. Creer un service systemd pour Hermes (si pas deja existant)
2. Le service doit demarrer Hermes avec le bon profil et les bons gateways
3. Ordre: apres ros2-llm-bridge.service

Si agent custom Python:
1. Creer un service systemd pour l'agent
2. Script Python qui boucle: message -> LLM -> tool call -> resultat -> reponse

**Modification**: Ajouter un service systemd `clawbot-agent.service`.

### 3.9. POINT IMPORTANT 9: Suppression d'OpenClaw

**Status**: NETTOYAGE.

Une fois le nouvel agent operationnel:
1. `npm uninstall -g openclaw` (suppression du package)
2. `rm -rf /home/jetson/.openclaw/` (suppression config + workspace)
3. Mettre a jour `WORKSPACE_PATH` dans le service hardware_service
4. Mettre a jour le `.env` si necessaire
5. Documenter dans la knowledge base

### 3.10. POINT IMPORTANT 10: Monitoring Dashboard

**Status**: VERIFICATION.

Le dashboard (clawbot_monitoring, port 5000) communique avec:
- `LLM_BRIDGE_URL=http://localhost:8000` (bridge)
- `HARDWARE_SERVICE_URL=http://localhost:8001` (hardware)

Ces URLs ne changent pas. Le dashboard continuera de fonctionner.

**Modification**: Aucune. Verifier seulement que le dashboard reste operationnel.

## 4. Plan d'Action Recommande

### Phase 1: Preparation (1-2h)
1. Creer le nouveau workspace: `mkdir /home/jetson/clawbot/workspace`
2. Mettre a jour `WORKSPACE_PATH` dans le service hardware_service
3. Redemarrer `ros2-hardware-service.service`
4. Verifier que `GET http://localhost:8000/tools` retourne bien les 17 tools
5. Tester `POST http://localhost:8000/command` avec un tool simple (GetBatteryVoltage)

### Phase 2: Configuration du Nouvel Agent (2-4h)
1. Configurer les providers LLM (codex/ollama)
2. Creer le system prompt robotique
3. Implementer le client HTTP qui fetch /tools et poste /command
4. Tester le function calling avec un model local (gemma4 ou qwen3.5)
5. Tester le traitement d'images (capture + analyse)

### Phase 3: Canaux de Communication (1-4h par canal)
1. Configurer les gateways (Telegram en premier)
2. Tester l'envoi de commandes depuis Telegram
3. Verifier le retour des resultats

### Phase 4: Service Systemd (30min)
1. Creer `clawbot-agent.service`
2. Tester le demarrage auto au boot
3. Verifier l'ordre des dependances

### Phase 5: Nettoyage (30min)
1. Arreter OpenClaw
2. Desinstaller openclaw npm
3. Supprimer /home/jetson/.openclaw/
4. Mettre a jour la knowledge base

## 5. Matrice d'Impact

| Composant | Impact | Action |
|-----------|--------|--------|
| ros2_llm_bridge (port 8000) | AUCUN | Pas touche |
| hardware_service (port 8001) | FAIBLE | Changer WORKSPACE_PATH |
| driver_node | AUCUN | Pas touche |
| Services systemd | FAIBLE | Ajouter clawbot-agent.service |
| Docker compose | AUCUN | Pas touche |
| Monitoring dashboard | AUCUN | Pas touche |
| rosbridge (Foxglove) | AUCUN | Pas touche |
| joy_teleop | AUCUN | Pas touche |
| OpenClaw | SUPPRESSION | Desinstaller + nettoyer |
| Workspace images | MIGRATION | Nouveau chemin |
| Config models | MIGRATION | Vers nouvel agent |
| System prompt | CREATION | Specialise robotique |
| Canaux messagerie | MIGRATION | Vers gateway nouvel agent |

## 6. Risques et Mitigations

| Risque | Probabilite | Impact | Mitigation |
|--------|-------------|--------|------------|
| Perte de credentials canaux | Moyenne | Eleve | Sauvegarder avant suppression OpenClaw |
| Models codex non reproductibles | Moyenne | Moyen | Utiliser ollama local en fallback |
| Workspace images perdues | Faible | Faible | Copier avant suppression |
| Dashboard casse | Faible | Faible | URLs ne changent pas |
| Service ne demarre pas | Moyenne | Eleve | Tester avant activation auto-start |

## 7. Recommandation

**Utiliser Hermes Agent** comme rempla d'OpenClaw, car:
- Deja installe et operationnel sur cette machine
- Supporte ollama local et providers openai-compatible
- A deja 60+ skills dont beaucoup correspondent
- Supporte les memes canaux (Telegram, Discord, etc.)
- Permet de creer un skill dedie "clawbot" avec le system prompt et le client HTTP
- Pas de dependance npm/Node.js supplementaire

L'alternative serait un script Python custom, mais cela necessiterait:
- Reinventer la gestion des canaux
- Reinventer le function calling
- Reinventer la gestion des models
- Plus de maintenance long terme