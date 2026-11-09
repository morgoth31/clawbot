---
title: "Skills — Méthodes formelles"
date: "2026-11-10T06:59:32+08:00"
author: "Hermes Agent"
tags: [skills, agent, hermes, formal-methods]
status: "actif"
generated: true
---


# Skills — Méthodes formelles

5 skill(s) disponibles dans cette catégorie. Page générée par `scripts/generate_skills_docs.py` depuis l'inventaire de l'agent ; ne pas éditer à la main.

Vérification déductive du C : ACSL, Frama-C/WP, Why3, Coq.

| Skill | Description | Entrées liées | Source |
|---|---|---|---|
| `acsl-spec` | Write, repair or strengthen ACSL annotations on C code — function contracts (requires, assigns, ensures, terminates, exits, behaviors), loop invarian… | 7 réf. | `~/.hermes/skills/formal-methods/acsl-spec/` |
| `acsl-verify` | Entry point for any ACSL/Frama-C/WP verification work on C code. Use when asked to verify, prove or formally check C, to "add specs and prove it", to… | — | `~/.hermes/skills/formal-methods/acsl-verify/` |
| `frama-c-wp` | Run and debug Frama-C/WP proofs of C code. Exact command lines, prover selection (Alt-Ergo, CVC4, CVC5, Z3, Coq), memory-model choice, RTE generation… | 6 réf. · 4 script(s) | `~/.hermes/skills/formal-methods/frama-c-wp/` |
| `verifiable-c` | Design and write new C that Frama-C/WP can actually prove, or refactor existing C to make it provable. Covers the constructs WP cannot handle (irredu… | 3 réf. | `~/.hermes/skills/formal-methods/verifiable-c/` |
| `wp-coq` | Write manual Coq proofs for Frama-C/WP goals that no SMT solver can close. Covers -wp-interactive update/batch, the edit contract for the generated .… | 2 réf. · 2 script(s) | `~/.hermes/skills/formal-methods/wp-coq/` |

Chargement par l'agent : `skill_view("<nom>")`, puis lecture d'une référence précise avec `skill_view("<nom>", "references/<fichier>.md")`.
