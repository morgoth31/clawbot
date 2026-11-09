---
title: "Skills — Superpowers (plugin)"
date: "2026-11-10T06:52:45+08:00"
author: "Hermes Agent"
tags: [skills, agent, hermes, superpowers]
status: "actif"
generated: true
---


# Skills — Superpowers (plugin)

15 skill(s) disponibles dans cette catégorie. Page générée par `scripts/generate_skills_docs.py` depuis l'inventaire de l'agent ; ne pas éditer à la main.

Skills fournis par le plugin superpowers, chargés sous le préfixe `superpowers:`.

| Skill | Description | Entrées liées | Source |
|---|---|---|---|
| `superpowers:brainstorming` | You MUST use this before any creative work - creating features, building components, adding functionality, modifying behavior, or planning anything n… | 5 script(s) | `~/.hermes/plugins/superpowers/skills/brainstorming/` |
| `superpowers:diagnosing-superpowers` | Use when a superpowers session went wrong and your human partner wants to know why — repeated work, ignored plans, stumbles, poor results, a skill th… | 4 réf. | `~/.hermes/plugins/superpowers/skills/diagnosing-superpowers/` |
| `superpowers:dispatching-parallel-agents` | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies | — | `~/.hermes/plugins/superpowers/skills/dispatching-parallel-agents/` |
| `superpowers:executing-plans` | Use when executing an implementation plan in the current session as the implementer yourself — your human partner chose inline execution, or no subag… | 2 script(s) | `~/.hermes/plugins/superpowers/skills/executing-plans/` |
| `superpowers:finishing-a-development-branch` | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work | — | `~/.hermes/plugins/superpowers/skills/finishing-a-development-branch/` |
| `superpowers:receiving-code-review` | Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires… | — | `~/.hermes/plugins/superpowers/skills/receiving-code-review/` |
| `superpowers:requesting-code-review` | Use when completing tasks, implementing major features, or before merging to verify work meets requirements | — | `~/.hermes/plugins/superpowers/skills/requesting-code-review/` |
| `superpowers:subagent-driven-development` | Use when executing implementation plans with independent tasks in the current session | 7 réf. · 4 script(s) | `~/.hermes/plugins/superpowers/skills/subagent-driven-development/` |
| `superpowers:systematic-debugging` | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes | — | `~/.hermes/plugins/superpowers/skills/systematic-debugging/` |
| `superpowers:test-driven-development` | Use when implementing any feature or bugfix, before writing implementation code | — | `~/.hermes/plugins/superpowers/skills/test-driven-development/` |
| `superpowers:using-git-worktrees` | Use when starting feature work that needs isolation from current workspace or before executing implementation plans - ensures an isolated workspace e… | — | `~/.hermes/plugins/superpowers/skills/using-git-worktrees/` |
| `superpowers:using-superpowers` | Use when starting any conversation - establishes how to find and use skills, requiring skill invocation before ANY response including clarifying ques… | 7 réf. | `~/.hermes/plugins/superpowers/skills/using-superpowers/` |
| `superpowers:verification-before-completion` | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirmin… | — | `~/.hermes/plugins/superpowers/skills/verification-before-completion/` |
| `superpowers:writing-plans` | Use when you have a spec or requirements for a multi-step task, before touching code | — | `~/.hermes/plugins/superpowers/skills/writing-plans/` |
| `superpowers:writing-skills` | Use when creating new skills, editing existing skills, or verifying skills work before deployment | 8 réf. | `~/.hermes/plugins/superpowers/skills/writing-skills/` |

Chargement par l'agent : `skill_view("<nom>")`, puis lecture d'une référence précise avec `skill_view("<nom>", "references/<fichier>.md")`.
