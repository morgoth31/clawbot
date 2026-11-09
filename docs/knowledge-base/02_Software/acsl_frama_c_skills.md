---
title: "acsl-skills — vérification formelle du C (ACSL, Frama-C/WP, Why3, Coq)"
date: "2026-11-10T07:00:00+08:00"
author: "Hermes Agent"
tags: [software, formal-methods, acsl, frama-c, wp, why3, coq, verification, skills]
status: validé
---

# acsl-skills — vérification formelle du C

Jeu de cinq skills pour la vérification déductive de code C avec Frama-C et son greffon WP :
écriture des annotations ACSL, exécution et triage des preuves, écriture de C prouvable, et
preuves Coq en dernier recours. Retour à l'[[index]]. Inventaire des skills : `docs/skills/formal-methods.md`
du dépôt, menu **Skills** du site.

## 1. Identification

| Élément | Valeur |
|---|---|
| Dépôt | `https://github.com/evdenis/acsl-skills` |
| Version | 1.1.0 (`chore: release v1.1.0`) |
| Commit installé | `771cf92` |
| Licence | MIT |
| Format | Agent Skills (un `SKILL.md` par compétence, `agents/`, `references/`, `assets/`, `scripts/`) |
| Taille installée | 372 Ko |
| Emplacement | `~/.hermes/skills/formal-methods/` |
| Méthode | copie des cinq répertoires de `skills/` (les liens `.claude/skills` et `.agents/skills` du dépôt ne sont pas utilisés) |

Les cinq compétences doivent rester côte à côte : plusieurs renvois pointent vers les
`references/` d'un autre skill (`frama-c-wp/references/triage.md`).

## 2. Les cinq skills

| Skill | Rôle | Renvois internes |
|---|---|---|
| `acsl-verify` | Point d'entrée : boucle annoter → exécuter → trier → renforcer, échelle d'escalade SMT → fonction-lemme → Coq, définition de « terminé » | 0 référence (routage) |
| `acsl-spec` | Écrire, réparer ou renforcer les annotations ACSL : contrats (`requires`, `assigns`, `ensures`, `terminates`, `exits`, `behaviors`), invariants et variants de boucle, prédicats, fonctions logiques, lemmes, code fantôme, étiquettes `\at` | 7 références (`contracts.md`, `loops.md`, `logic-defs.md`, `memory-labels.md`, `patterns.md`, `parsers.md`, `builtins.md`) |
| `frama-c-wp` | Exécuter et déboguer WP : lignes de commande exactes, choix des prouveurs (Alt-Ergo, CVC4, CVC5, Z3, Coq), modèle mémoire, génération RTE, cache de preuve, exploration d'un but, table de triage des messages d'erreur | 6 références, 4 scripts (`wp.sh`, `wp-smoke.sh`, `wp-goal.sh`, `env.sh`) |
| `verifiable-c` | Concevoir du C que WP peut prouver, ou décider si du C est vérifiable : constructions non supportées (boucles `goto` irréductibles, casts de pointeurs, unions, `malloc`, `container_of`, pointeurs de fonction), style prouvable, disposition de projet | 3 références |
| `wp-coq` | Preuves Coq manuelles des buts qu'aucun solveur SMT ne ferme : `-wp-interactive update/batch`, contrat d'édition du fichier `.v`, mangling ACSL → Coq (`L_`, `P_`, `Q_`), vocabulaire du modèle mémoire `Typed`, itération `coqtop` sans interface | 2 références, 2 scripts (`coq-iter.sh`, `env.sh`) |

## 3. Prérequis et état sur ce poste

| Prérequis exigé par les skills | Version demandée | État constaté le 2026-11-10 06:57 CST |
|---|---|---|
| `frama-c` avec greffon WP | Frama-C 33 | Donnée non disponible — `command -v frama-c` sans sortie (code 1) |
| `why3` | non versionné | Donnée non disponible — absent du `PATH` |
| `alt-ergo` | au moins un proueur | Donnée non disponible — absent du `PATH` |
| `z3`, `cvc5` | recommandés | Donnée non disponible — absents du `PATH` |
| `coqc` / `why3-coq` | Coq 8.20 (skill `wp-coq`) | Donnée non disponible — absents du `PATH` |
| `opam` | installation recommandée par le dépôt | Donnée non disponible — absent du `PATH` |
| Paquet système `frama-c` | — | Aucun candidat (`apt-cache policy frama-c` sans sortie) |

Conséquence vérifiée : le script d'exécution échoue proprement, sans faux succès.

```
$ bash ~/.hermes/skills/formal-methods/frama-c-wp/scripts/wp.sh /dev/null
no frama-c found.
  Set FRAMAC_SWITCH=<opam switch>, or put frama-c on PATH.
exit=2
```

Aucune preuve ne peut donc être produite sur ce poste : tout résultat WP est
« Donnée non disponible » avec le code de sortie 2 du script `wp.sh`.

## 4. Vérification de l'intégration

| Contrôle | Résultat |
|---|---|
| Découverte par Hermes | `skills_list(category="formal-methods")` retourne les 5 skills avec leurs descriptions complètes |
| Chargement | `skill_view("acsl-verify")` expose le corps et les fichiers liés ; idem pour les quatre autres |
| Cohérence du jeu de skills | `bash tools/check-docs.sh -q` → `check-docs: OK` (les cinq valident, scripts parsés, préambule d'environnement présent) |
| Validateur Codex | `ok — all five valid for Codex` |
| Validateur agentskills.io | `skip — agentskills not available (pip install skills-ref)` |
| Validateur de manifeste Claude | `skip — claude not on PATH` |

Remarque d'exécution : le premier lancement de `check-docs.sh` retournait cinq échecs
`ModuleNotFoundError: No module named 'yaml'`. Cause : le `python3` du `PATH` de la session est
celui du venv Hermes (3.14, sans PyYAML), alors que le script de validation suppose un interpréteur
disposant de PyYAML. Relancé avec `PATH=/usr/bin:/bin:/usr/sbin:/sbin`, le contrôle passe
intégralement. Ce n'est pas un défaut du jeu de skills.

## 5. Emploi sous Hermes

| Action | Commande |
|---|---|
| Charger le point d'entrée | `skill_view("acsl-verify")` |
| Charger une compétence précise | `skill_view("acsl-spec")`, `skill_view("frama-c-wp")` |
| Lire une référence du skill courant | `skill_view("frama-c-wp", "references/triage.md")` |
| Lire une référence d'un skill voisin | `read_file("~/.hermes/skills/formal-methods/frama-c-wp/references/triage.md")` |
| Exécuter WP | `bash ~/.hermes/skills/formal-methods/frama-c-wp/scripts/wp.sh <fichier.c>` |
| Contrôle de vacuité | `bash …/wp.sh` puis `bash …/wp-smoke.sh <fichier.c>` (seulement après un code 0) |

Le champ `allowed-tools` des skills `frama-c-wp` et `wp-coq` est propre au client Claude
(`Bash(${CLAUDE_SKILL_DIR}/scripts/…)`) ; Hermes ne l'exploite pas : l'exécution passe par l'outil
`terminal` avec le chemin absolu des scripts.

## 6. Applicabilité à ce robot

| Constat | Valeur |
|---|---|
| Fichiers `.c` dans le dépôt `clawbot` | 0 |
| Fichiers `.cpp` / `.hpp` dans le dépôt `clawbot` | 32 |

Le jeu de skills cible le langage C ; la pile actuelle du robot est en Python et C++ (pont LLM,
nœuds ROS 2, [[yahboomcar_bringup_driver_node]]). Aucun code C n'existe à ce jour dans le dépôt :
la vérification formelle n'a pas de cible immédiate. Cibles possibles si du C est introduit :
micrologiciel de la carte de commande, moniteur de sécurité en C, ou noyau Linux modifié.

## 7. Limites

| Limite | Conséquence |
|---|---|
| Chaîne de preuve absente | Aucune exécution de WP, Why3 ou Coq possible sans installation d'opam et Frama-C 33 |
| Version exigée précise | Frama-C 33 est requis ; une version antérieure n'est pas couverte par les skills |
| C uniquement | Pas d'ACSL pour le C++ ; le code du pont LLM reste hors périmètre |
| Validateurs propres aux clients | Les hooks et validateurs Claude/Codex ne s'exécutent pas sous Hermes |

## 8. Voir aussi

- Inventaire des skills publié : `docs/skills/formal-methods.md` (menu **Skills** du site, port 8080)
- Pont LLM et son analyse : [[llm2ros_bridge]], [[llm2ros_bridge_coherence_et_approche]]
- Skill et validateurs ROS 2 installés : [[ros2_engineering_skills]]
- Graphe ROS 2 : [[ros2_graph_clawbot]]
