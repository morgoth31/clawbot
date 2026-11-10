---
title: "Skills — Agents autonomes"
date: "2026-11-10T13:25:44+08:00"
author: "Hermes Agent"
tags: [skills, agent, hermes, autonomous-ai-agents]
status: "actif"
generated: true
---


# Skills — Agents autonomes

6 skill(s) disponibles dans cette catégorie. Page générée par `scripts/generate_skills_docs.py` depuis l'inventaire de l'agent ; ne pas éditer à la main.

Délégation à des agents externes (Claude Code, Codex, OpenCode).

| Skill | Description | Entrées liées | Source |
|---|---|---|---|
| `claude-code` | Delegate coding to Claude Code CLI (features, PRs). | — | `~/.hermes/skills/autonomous-ai-agents/claude-code/` |
| `codex` | Delegate coding to OpenAI Codex CLI (features, PRs). | — | `~/.hermes/skills/autonomous-ai-agents/codex/` |
| `computer-use` | Drive the desktop background-first; escalate on signal. | — | `~/.hermes/skills/autonomous-ai-agents/computer-use/` |
| `hermes-agent` | Use, configure, theme, extend, and orchestrate Hermes Agent. | 20 réf. | `~/.hermes/skills/autonomous-ai-agents/hermes-agent/` |
| `opencode` | Delegate coding to OpenCode CLI (features, PR review). | — | `~/.hermes/skills/autonomous-ai-agents/opencode/` |
| `skill-repo-install` | Use when installing skills from an external Git repo. | 1 réf. | `~/.hermes/skills/autonomous-ai-agents/skill-repo-install/` |

Chargement par l'agent : `skill_view("<nom>")`, puis lecture d'une référence précise avec `skill_view("<nom>", "references/<fichier>.md")`.
