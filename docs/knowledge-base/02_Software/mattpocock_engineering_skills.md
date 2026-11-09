---
title: "mattpocock/skills — skills d'ingénierie système (flux idée → livraison)"
date: "2026-11-10T07:24:00+08:00"
author: "Hermes Agent"
tags: [software, skills, ingenierie, workflow, spec, tickets, tdd, revue]
status: validé
---

# mattpocock/skills — skills d'ingénierie système

Jeu de skills d'ingénierie logicielle : cadrage par entretien, spécification, découpage en tickets,
implémentation, revue à deux axes, triage et rétrospective. Retour à l'[[index]]. Inventaire publié :
`docs/skills/systems-engineering.md` et `docs/skills/productivity.md` (menu **Skills** du site).

## 1. Identification

| Élément | Valeur |
|---|---|
| Dépôt | `https://github.com/mattpocock/skills` |
| Commit installé | `4ae2317` (`software-factory: glossary skill…`) |
| Licence | MIT |
| Contenu retenu | 20 skills de `skills/engineering` + 7 de `skills/productivity` cités par le flux |
| Emplacements | `~/.hermes/skills/systems-engineering/` (20) et `~/.hermes/skills/productivity/` (7 ajoutés aux 16 existants) |
| Taille | 512 Ko (ingénierie), 7 dossiers supplémentaires en productivité |
| Format | `SKILL.md` + fichiers annexes (formats, gabarits, scripts) et `agents/openai.yaml` (métadonnées d'interface propres à d'autres clients) |

## 2. Le flux principal : idée → livraison

Le skill `ask-matt` joue le rôle de routeur et décrit la séquence que les autres skills supposent.

| Étape | Skill | Rôle |
|---|---|---|
| 1. Cadrer | `grill-with-docs` (ou `grill-me`) | Entretien serré qui durcit l'idée et laisse une trace dans `GLOSSARY.md` et des ADR |
| 2. Trancher une question par du code jetable | `prototype` (précédé de `handoff`) | Prototype jetable pour répondre à une question d'état, de logique ou d'UI |
| 3. Spécifier | `to-spec` | Synthèse de la conversation en spécification publiée dans le tracker |
| 4. Découper | `to-tickets` | Tickets « tracer bullet » avec leurs arêtes de blocage |
| 5. Construire | `implement`, `implement-spec`, `tdd` | Implémentation ticket par ticket ou en orchestration parallèle ; boucle rouge-vert-refactor |
| 6. Relire | `code-review` | Revue à deux axes (Standards et Spec) sur le diff depuis un point fixe |
| 7. Publier | `pr` | Corps de pull request : plus petite vue utile, preuve avant/après, caractère réversible ou non |
| 8. Clore | `retro` | Rétrospective sur la session, qui propose des changements d'environnement, pas de code |
| Transverse | `wayfinder` | Planification d'un chantier trop gros pour une session, en tickets de décision |

Deux skills de vocabulaire accompagnent le flux : `codebase-design` (modules profonds, interfaces,
coutures) et `domain-modeling` (glossaire, ADR). `improve-codebase-architecture` produit un rapport
HTML des occasions d'approfondissement. `diagnosing-bugs` est la boucle de diagnostic des anomalies
dures et des régressions de performance. `wizard` génère un assistant bash pour les étapes qu'un
humain seul peut exécuter. `setup-matt-pocock-skills` prépare un dépôt (tracker, vocabulaire de
triage, emplacement des documents de domaine).

## 3. Skills de productivité ajoutés en complément

Le flux cite des skills qui ne sont pas dans `skills/engineering` ; ils ont été installés pour que
les renvois aboutissent :

| Skill | Rôle | Cité par |
|---|---|---|
| `grilling` | Primitive d'entretien serré | `grill-with-docs`, `triage`, `wayfinder` |
| `grill-me` | Entretien serré hors dépôt | `ask-matt` |
| `handoff` | Compacte la conversation en document de passation | `ask-matt`, `grill-with-docs` |
| `teach` | Enseigne un concept dans le contexte du dépôt | `ask-matt` |
| `to-questionnaire` | Transforme une décision non tranchable en questionnaire | `triage` |
| `wait-what` | Fait reformuler un message qui n'a pas fonctionné | `ask-matt` |
| `writing-for-agents` | Écrit des documents destinés à des agents | `ask-matt` |

## 4. Prérequis et état sur ce poste

| Prérequis | État constaté le 2026-11-10 07:20 CST | Effet |
|---|---|---|
| `gh` (GitHub CLI) | Donnée non disponible — absent du `PATH` ; paquet Ubuntu candidat `2.4.0+dfsg1-2` | `triage`, `to-spec`, `to-tickets`, `wayfinder`, `pr` ne peuvent pas passer par GitHub |
| Tracker configuré | Non configuré | `setup-matt-pocock-skills` doit être lancé une fois par dépôt |
| Tracker local de repli | Disponible (`issue-tracker-local.md` fourni) | Le flux fonctionne sans `gh`, avec un fichier par ticket sous `.scratch/<feature>/issues/` |
| Git | Présent | Suffisant pour `code-review` (revue depuis un point fixe) |

Le flux reste donc utilisable ici en mode tracker local ; seule la variante GitHub (issues, PR,
liens de blocage natifs) exige `gh`.

## 5. Chevauchement avec les skills déjà installés

Trois familles se recouvrent désormais. Règle d'arbitrage retenue pour ce dépôt :

| Besoin | Skill à utiliser | Pourquoi |
|---|---|---|
| Boucle rouge-vert-refactor dans une session de travail sur ce robot | `superpowers:test-driven-development` | Déjà employé ici, cohérent avec `superpowers:verification-before-completion` |
| Conseils test-first ciblés (mocking, tests d'intégration) | `tdd` | Fournit `mocking.md` et `tests.md`, plus granulaires |
| Revue avant commit d'un changement local | `requesting-code-review` (installé) ou `superpowers:requesting-code-review` | Chaîne de revue déjà outillée ici |
| Revue d'une branche ou d'une PR contre un point fixe, à deux axes | `code-review` | Seul à séparer Standards et Spec et à lancer deux sous-agents |
| Revue d'une PR GitHub avec commentaires en ligne | `github-code-review` | Passe par `gh` et l'API REST |
| Vérifier une intuition par du code jetable | `prototype` (ou `spike`) | `prototype` impose un dossier séparé et une question explicite |

## 6. Vérification de l'installation

| Contrôle | Résultat |
|---|---|
| Découverte (ingénierie) | `skills_list(category="systems-engineering")` → 20 skills, descriptions complètes |
| Découverte (productivité) | catégorie `productivity` → 23 skills (16 préexistants + 7 ajoutés) |
| Chargement | `skill_view("pr")` → 170 lignes, gabarit de corps de PR avec diagrammes Mermaid |
| Collisions de noms | Aucune avec les 93 dossiers de skills déjà présents |
| Références entre skills | Aucun chemin relatif `../` : les renvois se font par nom, donc la répartition sur deux catégories ne casse rien |
| Total après installation | 130 skills exposés (115 installés + 15 du plugin superpowers) |

## 7. Limites

| Limite | Conséquence |
|---|---|
| Flux pensé pour un tracker d'issues | Sans `setup-matt-pocock-skills`, les skills de spec et de tickets n'ont pas de destination |
| Sessions longues | Le flux suppose un contexte non compacté entre le cadrage et les tickets ; il documente lui-même la limite de la « smart zone » |
| Scripts gabarits | `wizard/template.sh`, `diagnosing-bugs/scripts/hitl-loop.template.sh` sont des modèles à adapter |
| Métadonnées d'interface | `agents/openai.yaml` et les invocations `/nom` sont propres à d'autres clients ; sous Hermes, l'appel se fait par nom de skill |
| Aucun hook | Pas de contrôle automatique : la discipline repose sur le chargement explicite des skills |

## 8. Voir aussi

- Inventaire généré : `docs/skills/systems-engineering.md`, `docs/skills/productivity.md`
- Skills ROS 2 installés : [[ros2_engineering_skills]]
- Skills de vérification formelle : [[acsl_frama_c_skills]]
- Pont LLM et son analyse : [[llm2ros_bridge]], [[llm2ros_bridge_coherence_et_approche]]
- Conventions de documentation : [[index]]
