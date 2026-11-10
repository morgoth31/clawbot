# Agent Hermes — ce qui tourne côté Système 2

Hermes est l'agent de raisonnement du robot : il intervient **sur sollicitation** du Système 1,
lit le contexte d'un incident par le serveur MCP, propose ou exécute une action encadrée, et
documente ce qu'il fait dans la base de connaissances.

## Rôle dans l'architecture

| Attribut | Valeur |
|---|---|
| Position | Système 2 — hors de la boucle de contrôle |
| Déclenchement | incident émis par S1, ou demande explicite de l'opérateur |
| Accès aux actions | outils MCP du pont (`param_*`, `goal_*`, `safety_stop`, `escalate`) |
| Interdictions | publier sur un actionneur, exécuter du code sur le robot sans passer par l'arbitre, élargir son propre jeu d'outils |
| Traces | base OKF (`/Robot_Knowledge_Base`), journal d'audit du pont, historique de session |

## Skills — mémoire procédurale

Un skill est une procédure réutilisable, chargée uniquement quand la tâche la concerne : commandes
exactes, pièges connus, standards de qualité. Les skills sont la mémoire de méthode de l'agent ; la
mémoire persistante ne garde que les faits valables dans toutes les sessions.

| Indicateur | Valeur |
|---|---|
| Skills installés | **130** |
| Catégories | 19 |
| Emplacement | `~/.hermes/skills/<catégorie>/<skill>/SKILL.md` |
| Plugin externe | `superpowers` (obra/superpowers v7.0.2, 15 skills) |
| Génération des pages | `scripts/generate_skills_docs.py` → `docs/skills/` et bloc de navigation |

### Skills qui comptent pour ce robot

| Skill | Usage sur ce poste |
|---|---|
| `robot-knowledge-base` | format OKF, validateur `scripts/validate_okf.py`, vérification Mermaid |
| `ros2-engineering-skills` | audit QoS, validation de launch, contrat de skills (1 819 tests) |
| `ros2-mcp-bridge` | conception et test du pont : contrat MCP, déclencheurs, pièges du SDK |
| `formal-methods/*` (5) | spécification ACSL et preuve Frama-C/WP — installés, non exécutables (voir [[bom_logiciel]]) |
| `systems-engineering/*` (20) | `to-spec`, `to-tickets`, `tdd`, `code-review`, `implement` |
| `superpowers:*` (15) | brainstorm, plans, debug systématique, revue |

Le catalogue complet, catégorie par catégorie, est dans [Skills — vue d'ensemble](skills/index.md).
Chaque page de catégorie liste les skills avec leur description, leurs fichiers liés et leur source.

### Installer un skill depuis un dépôt

```bash
git clone <dépôt> /tmp/skills-src
cp -r /tmp/skills-src/<chemin>/<skill> ~/.hermes/skills/<catégorie>/
python3 scripts/generate_skills_docs.py        # régénère les pages et la navigation
python3 ~/.hermes/skills/robotics/robot-knowledge-base/scripts/validate_okf.py
```

Un skill installé sans page régénérée reste invisible dans la documentation : la génération fait
partie de l'installation, pas d'une étape facultative.

## Outils et configuration

| Élément | Emplacement | Remarque |
|---|---|---|
| Configuration | `~/.hermes/config.yaml` | modèle, mémoire, skills, subagents |
| Skills | `~/.hermes/skills/` | 130 skills, 19 catégories |
| Plugins | `~/.hermes/plugins/superpowers` | activé ; retour arrière par `hermes plugins disable superpowers` |
| Mémoire persistante | `~/.hermes/memories/` | faits durables uniquement, budget en caractères |
| Serveur MCP du pont | `mcp_servers.clawbot` (à déclarer) | outils exposés sous `mcp_clawbot_*` |
| Documents produits | `/Robot_Knowledge_Base` → `~/clawbot/docs/knowledge-base` | source unique, versionnée |

## Règles de conduite appliquées sur ce poste

- **Aucun secret dans la conversation.** Les jetons vivent dans des fichiers à droits restreints
  (`/etc/clawbot/*-token`, 600). Un secret montré dans un message est considéré comme compromis.
- **Aucune supposition silencieuse.** Un paramètre d'architecture manquant devient une question
  numérotée (D-xx), pas une valeur choisie sans le dire.
- **Aucune donnée inventée.** Une mesure impossible est écrite « Donnée non disponible » avec son
  code ; jamais un zéro, jamais une estimation présentée comme une mesure.
- **Traçabilité.** Toute modification de code référence l'exigence qui la justifie et le test qui
  la vérifie ([[llm2ros_traceabilite]]).

## Voir aussi

- [Skills — vue d'ensemble](skills/index.md)
- [Section Bridge](../bridge/index.md) — ce que l'agent manipule côté robot
- [Poste de documentation](../site-documentation.md) — comment ce site est construit et publié
