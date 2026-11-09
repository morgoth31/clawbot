---
title: "Skills de l'agent Hermes"
date: "2026-11-10T07:21:20+08:00"
author: "Hermes Agent"
tags: [skills, agent, hermes, inventaire]
status: "actif"
generated: true
---


# Skills de l'agent Hermes

Inventaire des skills chargés par l'agent sur ce robot. Chaque skill est un dossier contenant un `SKILL.md` (procédure) et, le cas échéant, des `references/` et des `scripts/`.

| Indicateur | Valeur |
|---|---|
| Skills installés | 115 |
| Skills fournis par un plugin | 15 |
| Catégories | 19 |
| Total | 130 |

## Chargement

L'agent n'exécute pas les skills comme un script : il les charge à la demande.

```text
skill_view("nom-du-skill")                        # corps du SKILL.md
skill_view("nom-du-skill", "references/x.md")      # référence ciblée
skill_view("superpowers:brainstorming")            # skill fourni par un plugin
```

## Catégories

| Catégorie | Skills | Page |
|---|---|---|
| Robotique | 2 | [Robotique](robotics.md) |
| Méthodes formelles | 5 | [Méthodes formelles](formal-methods.md) |
| Ingénierie système | 20 | [Ingénierie système](systems-engineering.md) |
| Apple | 4 | [Apple](apple.md) |
| Agents autonomes | 5 | [Agents autonomes](autonomous-ai-agents.md) |
| Créatif | 16 | [Créatif](creative.md) |
| DevOps | 1 | [DevOps](devops.md) |
| Courriel | 2 | [Courriel](email.md) |
| GitHub | 6 | [GitHub](github.md) |
| Médias | 3 | [Médias](media.md) |
| MLOps | 5 | [MLOps](mlops.md) |
| Prise de notes | 1 | [Prise de notes](note-taking.md) |
| Productivité | 23 | [Productivité](productivity.md) |
| Recherche | 6 | [Recherche](research.md) |
| Domotique | 1 | [Domotique](smart-home.md) |
| Réseaux sociaux | 1 | [Réseaux sociaux](social-media.md) |
| Développement logiciel | 13 | [Développement logiciel](software-development.md) |
| Superpowers (plugin) | 15 | [Superpowers (plugin)](superpowers.md) |
| Web | 1 | [Web](web.md) |

## Ajouter ou retirer un skill

```bash
# skill installé dans le profil
cp -r mon-skill ~/.hermes/skills/<catégorie>/

# régénérer cette documentation
python3 scripts/generate_skills_docs.py
sudo systemctl restart clawbot-docs.service
```

Un skill doit contenir un `SKILL.md` avec un frontmatter `name` et `description` : la description sert à l'agent pour choisir le skill, elle doit tenir en une phrase.

## Voir aussi

- [Poste de documentation](../site-documentation.md)
- [Base de connaissances](../knowledge-base/index.md)