---
title: "Skills — Ingénierie système"
date: "2026-11-10T07:20:58+08:00"
author: "Hermes Agent"
tags: [skills, agent, hermes, systems-engineering]
status: "actif"
generated: true
---


# Skills — Ingénierie système

20 skill(s) disponibles dans cette catégorie. Page générée par `scripts/generate_skills_docs.py` depuis l'inventaire de l'agent ; ne pas éditer à la main.

Flux d'ingénierie logicielle : cadrage, spec, tickets, implémentation, revue, triage.

| Skill | Description | Entrées liées | Source |
|---|---|---|---|
| `ask-matt` | Ask which skill or flow fits your situation. A router over the skills in this repo. | — | `~/.hermes/skills/systems-engineering/ask-matt/` |
| `code-review` | Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes: Standards (does the code follow this repo's documented co… | — | `~/.hermes/skills/systems-engineering/code-review/` |
| `codebase-design` | Shared vocabulary for designing deep modules. Use when the user wants to design or improve a module's interface, find deepening opportunities, decide… | — | `~/.hermes/skills/systems-engineering/codebase-design/` |
| `diagnosing-bugs` | Diagnosis loop for hard bugs and performance regressions. Use when the user says "diagnose"/"debug this", or reports something broken/throwing/failin… | 1 script(s) | `~/.hermes/skills/systems-engineering/diagnosing-bugs/` |
| `domain-modeling` | Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a GLOSSARY.md, or recording or editing an AD… | — | `~/.hermes/skills/systems-engineering/domain-modeling/` |
| `grill-with-docs` | A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go. | — | `~/.hermes/skills/systems-engineering/grill-with-docs/` |
| `implement` | Implement a piece of work based on a spec or set of tickets. | — | `~/.hermes/skills/systems-engineering/implement/` |
| `implement-spec` | Implement the result of /to-spec and /to-tickets in code. | — | `~/.hermes/skills/systems-engineering/implement-spec/` |
| `improve-codebase-architecture` | Scan a codebase for deepening opportunities, present them as a visual HTML report, then grill through whichever one you pick. | — | `~/.hermes/skills/systems-engineering/improve-codebase-architecture/` |
| `pr` | Use when writing a PR body. | — | `~/.hermes/skills/systems-engineering/pr/` |
| `prototype` | Build a throwaway prototype to answer a design question. Use when the user wants to sanity-check whether a state model or logic feels right, or explo… | — | `~/.hermes/skills/systems-engineering/prototype/` |
| `research` | Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the repo. Use when the user wants a topic re… | — | `~/.hermes/skills/systems-engineering/research/` |
| `retro` | Conduct a retrospective on a coding session. | — | `~/.hermes/skills/systems-engineering/retro/` |
| `setup-matt-pocock-skills` | Configure this repo for the engineering skills: set up its issue tracker, triage label vocabulary, and domain doc layout. Run once before first use o… | — | `~/.hermes/skills/systems-engineering/setup-matt-pocock-skills/` |
| `tdd` | Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests. | — | `~/.hermes/skills/systems-engineering/tdd/` |
| `to-spec` | Turn the current conversation into a spec and publish it to the project issue tracker: no interview, just synthesis of what you've already discussed. | — | `~/.hermes/skills/systems-engineering/to-spec/` |
| `to-tickets` | Break a plan, spec, or the current conversation into a set of tracer-bullet tickets, each declaring its blocking edges, published to the configured t… | — | `~/.hermes/skills/systems-engineering/to-tickets/` |
| `triage` | Move issues and external PRs through a state machine of triage roles, categorise, verify, grill if needed, and write agent-ready briefs. | — | `~/.hermes/skills/systems-engineering/triage/` |
| `wayfinder` | Plan a huge chunk of work (more than one agent session can hold) as a shared map of decision tickets on your issue tracker, and resolve them one at a… | — | `~/.hermes/skills/systems-engineering/wayfinder/` |
| `wizard` | Generate an interactive bash wizard that walks a human through steps only they can perform. Use when provisioning infrastructure, setting up credenti… | — | `~/.hermes/skills/systems-engineering/wizard/` |

Chargement par l'agent : `skill_view("<nom>")`, puis lecture d'une référence précise avec `skill_view("<nom>", "references/<fichier>.md")`.
