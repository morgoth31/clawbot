#!/usr/bin/env python3
"""Génère les pages « Skills » du site depuis l'inventaire réel de l'agent.

Sources scannées :
  - $HERMES_HOME/skills/<catégorie>/<nom>/SKILL.md        (skills installés)
  - $HERMES_HOME/plugins/<plugin>/skills/<nom>/SKILL.md   (skills fournis par un plugin,
                                                           appelés <plugin>:<nom>)

Sorties :
  - docs/skills/index.md            vue d'ensemble + tableau des catégories
  - docs/skills/<catégorie>.md      un tableau par catégorie
  - bloc de navigation de mkdocs.yml entre les marqueurs skills-nav:start / skills-nav:end

Relancer le script après toute installation ou suppression de skill. Il est idempotent :
seuls les fichiers générés sont réécrits.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
OUT = DOCS / "skills"
MKDOCS = REPO / "mkdocs.yml"

LABELS = {
    "apple": "Apple",
    "autonomous-ai-agents": "Agents autonomes",
    "creative": "Créatif",
    "devops": "DevOps",
    "email": "Courriel",
    "formal-methods": "Méthodes formelles",
    "github": "GitHub",
    "media": "Médias",
    "mlops": "MLOps",
    "note-taking": "Prise de notes",
    "productivity": "Productivité",
    "research": "Recherche",
    "robotics": "Robotique",
    "smart-home": "Domotique",
    "social-media": "Réseaux sociaux",
    "software-development": "Développement logiciel",
    "web": "Web",
    "superpowers": "Superpowers (plugin)",
    "systems-engineering": "Ingénierie système",
}

INTRO = {
    "robotics": "Skills propres au robot : documentation OKF et ingénierie ROS 2.",
    "software-development": "Méthodes de développement : plans, revues, débogage, tests.",
    "formal-methods": "Vérification déductive du C : ACSL, Frama-C/WP, Why3, Coq.",
    "systems-engineering": "Flux d'ingénierie logicielle : cadrage, spec, tickets, implémentation, revue, triage.",
    "autonomous-ai-agents": "Délégation à des agents externes (Claude Code, Codex, OpenCode).",
    "superpowers": "Skills fournis par le plugin superpowers, chargés sous le préfixe `superpowers:`.",
}


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    return Path(env) if env else Path.home() / ".hermes"


def parse_frontmatter(text: str) -> dict:
    """Frontmatter YAML minimal : scalaires et blocs pliés (``>``)."""
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    data: dict[str, str] = {}
    key = None
    for raw in match.group(1).splitlines():
        if not raw.strip():
            continue
        if re.match(r"^[A-Za-z_][\w-]*:", raw):
            key, _, value = raw.partition(":")
            key = key.strip()
            value = value.strip()
            data[key] = "" if value in (">", "|", ">-", "|-") else value
        elif key and raw.startswith((" ", "\t")):
            data[key] = (data.get(key, "") + " " + raw.strip()).strip()
    for k, v in list(data.items()):
        data[k] = v.strip().strip("\"'") if isinstance(v, str) else v
    return data


def collect() -> list[dict]:
    home = hermes_home()
    skills: list[dict] = []

    for path in sorted((home / "skills").rglob("SKILL.md")):
        rel = path.parent.relative_to(home / "skills")
        # Les dossiers cachés (.archive, sauvegardes) ne sont pas publiés.
        if any(part.startswith(".") for part in rel.parts):
            continue
        category = rel.parts[0] if len(rel.parts) > 1 else "divers"
        meta = parse_frontmatter(path.read_text(encoding="utf-8"))
        skills.append(
            {
                "name": meta.get("name") or path.parent.name,
                "category": category,
                "description": " ".join(meta.get("description", "").split()),
                "path": path,
                "source": f"~/.hermes/skills/{rel.as_posix()}/",
                "plugin": None,
            }
        )

    for path in sorted((home / "plugins").glob("*/skills/*/SKILL.md")):
        plugin = path.parents[2].name
        meta = parse_frontmatter(path.read_text(encoding="utf-8"))
        skills.append(
            {
                "name": f"{plugin}:{meta.get('name') or path.parent.name}",
                "category": plugin,
                "description": " ".join(meta.get("description", "").split()),
                "path": path,
                "source": f"~/.hermes/plugins/{plugin}/skills/{path.parent.name}/",
                "plugin": plugin,
            }
        )
    return skills


def linked_counts(skill: dict) -> str:
    base = skill["path"].parent
    refs = len(list((base / "references").glob("*"))) if (base / "references").is_dir() else 0
    scripts = len([p for p in (base / "scripts").glob("*") if p.is_file()]) if (base / "scripts").is_dir() else 0
    parts = []
    if refs:
        parts.append(f"{refs} réf.")
    if scripts:
        parts.append(f"{scripts} script(s)")
    return " · ".join(parts) or "—"


def shorten(text: str, limit: int = 150) -> str:
    text = text.replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def write_if_changed(path: Path, text: str) -> None:
    """N'écrit que si le contenu change, hors ligne `date` (évite le bruit Git)."""
    if path.exists():
        old = path.read_text(encoding="utf-8")
        strip = lambda s: re.sub(r"^date: .*$", "", s, flags=re.M)
        if strip(old) == strip(text):
            return
    path.write_text(text, encoding="utf-8")


def PRIORITY(category: str) -> tuple:
    """Robotique puis méthodes formelles en tête, le reste par ordre alphabétique."""
    rank = {"robotics": 0, "formal-methods": 1, "systems-engineering": 2}.get(category, 3)
    return (rank, category)


def category_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def frontmatter(title: str, tags: str) -> str:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    return (
        "---\n"
        f'title: "{title}"\n'
        f'date: "{stamp}"\n'
        'author: "Hermes Agent"\n'
        f"tags: [{tags}]\n"
        'status: "actif"\n'
        "generated: true\n"
        "---\n\n"
    )


def write_category_page(category: str, skills: list[dict]) -> str:
    slug = category_slug(category)
    label = LABELS.get(category, category.replace("-", " ").capitalize())
    body = [frontmatter(f"Skills — {label}", f"skills, agent, hermes, {slug}"), f"# Skills — {label}\n"]
    body.append(
        f"{len(skills)} skill(s) disponibles dans cette catégorie. "
        "Page générée par `scripts/generate_skills_docs.py` depuis l'inventaire de l'agent ; "
        "ne pas éditer à la main.\n"
    )
    if category in INTRO:
        body.append(f"{INTRO[category]}\n")
    body.append("| Skill | Description | Entrées liées | Source |")
    body.append("|---|---|---|---|")
    for skill in sorted(skills, key=lambda s: s["name"]):
        body.append(
            f"| `{skill['name']}` | {shorten(skill['description']) or '—'} | "
            f"{linked_counts(skill)} | `{skill['source']}` |"
        )
    body.append("")
    body.append(
        "Chargement par l'agent : `skill_view(\"<nom>\")`, puis lecture d'une référence précise "
        "avec `skill_view(\"<nom>\", \"references/<fichier>.md\")`.\n"
    )
    write_if_changed(OUT / f"{slug}.md", "\n".join(body))
    return slug


def write_index(skills: list[dict], slugs: dict[str, str]) -> None:
    by_cat: dict[str, list[dict]] = {}
    for skill in skills:
        by_cat.setdefault(skill["category"], []).append(skill)

    body = [
        frontmatter("Skills de l'agent Hermes", "skills, agent, hermes, inventaire"),
        "# Skills de l'agent Hermes\n",
        "Inventaire des skills chargés par l'agent sur ce robot. Chaque skill est un dossier "
        "contenant un `SKILL.md` (procédure) et, le cas échéant, des `references/` et des "
        "`scripts/`.\n",
        "| Indicateur | Valeur |",
        "|---|---|",
        f"| Skills installés | {sum(1 for s in skills if not s['plugin'])} |",
        f"| Skills fournis par un plugin | {sum(1 for s in skills if s['plugin'])} |",
        f"| Catégories | {len(by_cat)} |",
        f"| Total | {len(skills)} |",
        "",
        "## Chargement\n",
        "L'agent n'exécute pas les skills comme un script : il les charge à la demande.\n",
        "```text",
        "skill_view(\"nom-du-skill\")                        # corps du SKILL.md",
        "skill_view(\"nom-du-skill\", \"references/x.md\")      # référence ciblée",
        "skill_view(\"superpowers:brainstorming\")            # skill fourni par un plugin",
        "```\n",
        "## Catégories\n",
        "| Catégorie | Skills | Page |",
        "|---|---|---|",
    ]
    for category in sorted(by_cat, key=PRIORITY):
        label = LABELS.get(category, category.replace("-", " ").capitalize())
        body.append(f"| {label} | {len(by_cat[category])} | [{label}]({slugs[category]}.md) |")
    body.extend(
        [
            "",
            "## Ajouter ou retirer un skill\n",
            "```bash",
            "# skill installé dans le profil",
            "cp -r mon-skill ~/.hermes/skills/<catégorie>/",
            "",
            "# régénérer cette documentation",
            "python3 scripts/generate_skills_docs.py",
            "sudo systemctl restart clawbot-docs.service",
            "```\n",
            "Un skill doit contenir un `SKILL.md` avec un frontmatter `name` et `description` : "
            "la description sert à l'agent pour choisir le skill, elle doit tenir en une phrase.\n",
            "## Voir aussi\n",
            "- [Poste de documentation](../site-documentation.md)",
            "- [Base de connaissances](../knowledge-base/index.md)",
        ]
    )
    OUT.mkdir(parents=True, exist_ok=True)
    write_if_changed(OUT / "index.md", "\n".join(body))


def update_nav(slugs: dict[str, str]) -> None:
    lines = MKDOCS.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "# skills-nav:start")
    end = next(i for i, l in enumerate(lines) if l.strip() == "# skills-nav:end")
    indent = "      "  # sous-section de « Hermes (agent) » : 6 espaces
    block = [
        f'{indent}- "Skills — catalogue complet":',
        f"{indent}    - Vue d'ensemble: skills/index.md",
    ]
    for category in sorted(slugs, key=PRIORITY):
        label = LABELS.get(category, category.replace("-", " ").capitalize())
        block.append(f"{indent}    - {label}: skills/{slugs[category]}.md")
    lines[start + 1 : end] = block
    MKDOCS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    skills = collect()
    if not skills:
        print("aucun skill trouvé — vérifier HERMES_HOME", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    slugs: dict[str, str] = {}
    by_cat: dict[str, list[dict]] = {}
    for skill in skills:
        by_cat.setdefault(skill["category"], []).append(skill)
    for category, items in by_cat.items():
        slugs[category] = write_category_page(category, items)
    write_index(skills, slugs)
    update_nav(slugs)
    print(f"{len(skills)} skill(s), {len(by_cat)} catégorie(s) -> {OUT}")
    print("navigation mise à jour dans mkdocs.yml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
