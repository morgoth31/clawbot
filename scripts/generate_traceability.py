#!/usr/bin/env python3
"""Génère la matrice de traçabilité exigence → test (exigences TRC-01, TRC-02).

Source des exigences : les tableaux des documents de spécification de la base OKF.
Source des tests : le code de `tests/mcp_bridge`, analysé par `ast` (chaque fonction de test
est citée avec les identifiants qu'elle référence dans son nom, sa docstring ou son corps).

Sortie : `docs/knowledge-base/02_Software/llm2ros_traceabilite.md`, page OKF régénérée.

Aucune exigence n'est inventée : une exigence sans test est listée comme non couverte, et un
identifiant cité par un test mais absent des spécifications est listé comme orphelin.
"""

from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass, field
from pathlib import Path


def _iso8601(moment: time.struct_time | None = None) -> str:
    """ISO 8601 avec décalage horaire à deux points (+HH:MM), format exigé par le validateur OKF."""
    text = time.strftime("%Y-%m-%dT%H:%M:%S%z") if moment is None else time.strftime("%Y-%m-%dT%H:%M:%S%z", moment)
    return f"{text[:-2]}:{text[-2:]}" if len(text) >= 5 and text[-5] in "+-" else text
ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "docs" / "knowledge-base"
SPECS_DIR = KB / "02_Software"
TESTS_DIR = ROOT / "tests" / "mcp_bridge"
OUTPUT = SPECS_DIR / "llm2ros_traceabilite.md"

REQUIREMENT = re.compile(
    r"\b(?:MCP|TRG|CTX|SAF|TRC|HLT)-[A-Z]?\d{1,2}\b|\b(?:EF|NFR)-\d{1,2}\b"
)
FAMILIES = ("MCP", "TRG", "CTX", "SAF", "TRC", "HLT", "EF", "NFR")
#: identifiant volontairement inconnu utilisé par les tests pour vérifier le jeu clos (TRG-24)
SENTINELS = {"TRG-99"}

ROW = re.compile(
    r"^\|\s*((?:" + "|".join(FAMILIES) + r")-[A-Z]?\d{1,2})\s*\|\s*([^|]*)\|"
)


@dataclass
class Requirement:
    identifier: str
    text: str
    document: str
    tests: list[str] = field(default_factory=list)


def _clean(cell: str) -> str:
    text = cell.strip()
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"`", "", text)
    return text if len(text) <= 120 else text[:117] + "…"


def collect_requirements() -> dict[str, Requirement]:
    requirements: dict[str, Requirement] = {}
    for document in sorted(SPECS_DIR.glob("*.md")):
        if document.name in {"llm2ros_traceabilite.md"}:
            continue
        for line in document.read_text(encoding="utf-8").splitlines():
            match = ROW.match(line)
            if not match:
                continue
            identifier, text = match.group(1), _clean(match.group(2))
            if identifier not in requirements:
                requirements[identifier] = Requirement(identifier, text, document.name)
    return requirements


def collect_tests(requirements: dict[str, Requirement]) -> tuple[list[str], list[str]]:
    """Associe chaque test aux exigences qu'il cite ; retourne (fichiers, identifiants orphelins)."""
    files: list[str] = []
    orphans: set[str] = set()

    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        module = ast.parse(source)
        files.append(str(path.relative_to(ROOT)))
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            segment = ast.get_source_segment(source, node) or ""
            cited = set(REQUIREMENT.findall(node.name)) | set(REQUIREMENT.findall(segment))
            name = f"{path.stem}::{node.name}"
            for identifier in cited:
                if identifier in requirements:
                    requirements[identifier].tests.append(name)
                else:
                    orphans.add(identifier)

    return files, sorted(orphans)


def render(requirements: dict[str, Requirement], tests: list[str], orphans: list[str]) -> str:
    covered = [item for item in requirements.values() if item.tests]
    uncovered = [item for item in requirements.values() if not item.tests]
    stamp = _iso8601()
    generated = _iso8601()

    lines = [
        "---",
        'title: "Matrice de traçabilité — exigence vers test"',
        f'date: "{generated}"',
        'author: "Hermes Agent"',
        "tags: [software, tracabilite, tests, exigences, qualite]",
        "status: actif",
        "generated: true",
        "---",
        "",
        "# Matrice de traçabilité — exigence vers test",
        "",
        f"Page régénérée par `scripts/generate_traceability.py` le {stamp}. "
        "Elle ne se modifie pas à la main : toute évolution vient des spécifications ou des tests.",
        "",
        "## 1. Synthèse",
        "",
        "| Indicateur | Valeur |",
        "|---|---|",
        f"| Exigences identifiées | {len(requirements)} |",
        f"| Exigences couvertes par au moins un test | {len(covered)} |",
        f"| Exigences sans test | {len(uncovered)} |",
        f"| Fichiers de test analysés | {len(tests)} |",
        f"| Identifiants cités mais non spécifiés | {len(orphans)} |",
        "",
        "## 2. Matrice",
        "",
        "| Exigence | Énoncé | Document | Tests |",
        "|---|---|---|---|",
    ]

    for document in sorted({item.document for item in requirements.values()}):
        items = [item for item in requirements.values() if item.document == document]
        covered_here = sum(1 for item in items if item.tests)
        lines += [
            "",
            f"### {document} — {covered_here}/{len(items)} exigences citées par un test",
            "",
            "| Exigence | Énoncé | Tests |",
            "|---|---|---|",
        ]
        for item in sorted(items, key=lambda entry: _sort_key(entry.identifier)):
            tests_cell = ", ".join(f"`{name}`" for name in sorted(set(item.tests))) or "— **non couverte**"
            lines.append(f"| `{item.identifier}` | {item.text} | {tests_cell} |")

    lines += ["", "## 3. Exigences sans test", ""]
    if uncovered:
        lines.append("Ces exigences sont écrites mais aucune fonction de test ne les référence.")
        lines.append("")
        for item in sorted(uncovered, key=lambda entry: _sort_key(entry.identifier)):
            lines.append(f"- `{item.identifier}` — {item.text} (`{item.document}`)")
    else:
        lines.append("Aucune : toutes les exigences identifiées sont citées par au moins un test.")

    lines += ["", "## 4. Identifiants cités par les tests mais absents des spécifications", ""]
    lines.append("Les identifiants sentinelles (`TRG-99`) sont utilisés volontairement par les tests de jeu clos")
    lines.append("et ne sont pas des exigences manquantes.")
    lines.append("")
    real_orphans = [identifier for identifier in orphans if identifier not in SENTINELS]
    if real_orphans:
        lines.append("Un test qui cite un identifiant inconnu signale soit une coquille, soit une exigence")
        lines.append("supprimée du document : les deux cas demandent une correction.")
        lines.append("")
        for identifier in real_orphans:
            lines.append(f"- `{identifier}`")
    else:
        lines.append("Aucun : chaque identifiant cité par un test existe dans les spécifications.")

    lines += [
        "",
        "## 5. Limites de cette matrice",
        "",
        "- La couverture est **textuelle** : un test qui cite `MCP-04` vérifie un point de cette exigence,",
        "  pas nécessairement toute l'exigence. La revue humaine reste nécessaire.",
        "- Les exigences des documents historiques (`llm2ros_bridge_specification.md`) sont incluses ;",
        "  elles décrivent le pont C++ en service, pas le pont MCP en construction.",
        "- Les fichiers de test hors `tests/mcp_bridge` ne sont pas analysés.",
        "",
        "## 6. Voir aussi",
        "",
        "- [[llm2ros_mcp_specification]] — spécification de l'interface MCP et des déclencheurs",
        "- [[llm2ros_mcp_test_plan]] — architecture de la suite de tests",
        "- [[llm2ros_health_test_specification]] — exigences HLT",
        "- [[llm2ros_bridge_design]] — conception détaillée des modules",
        "",
    ]
    return "\n".join(lines)


def _sort_key(identifier: str) -> tuple[str, int, str]:
    family, _, number = identifier.partition("-")
    digits = re.sub(r"\D", "", number) or "0"
    return family, int(digits), number


def main() -> int:
    requirements = collect_requirements()
    tests, orphans = collect_tests(requirements)
    OUTPUT.write_text(render(requirements, tests, orphans), encoding="utf-8")
    covered = sum(1 for item in requirements.values() if item.tests)
    print(f"{OUTPUT.relative_to(ROOT)} : {len(requirements)} exigences, {covered} couvertes, "
          f"{len(orphans)} orphelines, {len(tests)} fichiers de test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
