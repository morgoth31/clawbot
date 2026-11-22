#!/usr/bin/env python3
"""Contrôle de traçabilité exigences <-> tests pour le dépôt Clawbot.

Lit requirements/*.yaml et les tests pytest (analyse AST, sans import ni exécution),
puis vérifie :
  1. format des exigences (identifiant, champs obligatoires, unicité) ;
  2. chaque exigence de méthode `test` est couverte par au moins un test marqué
     @pytest.mark.req("REQ-...") ;
  3. chaque marqueur `req` vise une exigence existante ;
  4. une exigence d'une autre méthode cite une preuve (`evidence`) qui existe ;
  5. une exigence `safety: true` déjà couverte par un test n'est plus en `draft`
     et porte `approved_by` (porte de validation humaine) ;
  6. optionnellement, le nombre de tests non tracés ne dépasse pas un plafond (cliquet).

Codes de sortie : 0 conforme, 1 non conforme, 2 erreur d'usage.
Dépendance : PyYAML (présent avec ROS 2).
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("trace_check: PyYAML est requis (python3-yaml).", file=sys.stderr)
    sys.exit(2)

REQ_ID = re.compile(r"^REQ-[A-Z]+-\d{3}$")
METHODS = {"test", "inspection", "analysis", "demonstration"}
LEVELS = {"unit", "integration", "hardware"}
STATUSES = ["draft", "approved", "implemented", "verified"]
REQUIRED = ("id", "title", "statement", "method", "level", "criterion", "status")
EXCLUDED_DIRS = {
    ".git", "install", "build", "log", "attic", "node_modules", "__pycache__",
    ".venv", "venv", ".pytest_cache",
}
EXCLUDED_SUBPATHS = ("tests/manual",)


@dataclass
class Requirement:
    id: str
    data: dict
    source: Path


@dataclass
class TestCase:
    nodeid: str
    reqs: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- exigences

def load_requirements(repo: Path, errors: list[str]) -> dict[str, Requirement]:
    reqs: dict[str, Requirement] = {}
    req_dir = repo / "requirements"
    if not req_dir.is_dir():
        errors.append("dossier requirements/ absent")
        return reqs
    for path in sorted(req_dir.glob("*.yaml")):
        if path.name.startswith("."):
            continue
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            errors.append(f"{path.name}: YAML invalide ({exc})")
            continue
        domain = doc.get("domain")
        items = doc.get("requirements") or []
        if not isinstance(items, list):
            errors.append(f"{path.name}: 'requirements' doit être une liste")
            continue
        for item in items:
            if not isinstance(item, dict):
                errors.append(f"{path.name}: entrée non conforme ({item!r})")
                continue
            rid = str(item.get("id", ""))
            missing = [k for k in REQUIRED if item.get(k) in (None, "")]
            if missing:
                errors.append(f"{path.name}: {rid or '?'} champs manquants : {', '.join(missing)}")
            if not REQ_ID.match(rid):
                errors.append(f"{path.name}: identifiant invalide '{rid}' (attendu REQ-DOMAINE-NNN)")
                continue
            if domain and rid.split("-")[1] != domain:
                errors.append(f"{path.name}: {rid} n'appartient pas au domaine {domain}")
            if rid in reqs:
                errors.append(f"{rid} défini deux fois ({reqs[rid].source.name}, {path.name})")
                continue
            if item.get("method") not in METHODS:
                errors.append(f"{rid}: méthode '{item.get('method')}' inconnue {sorted(METHODS)}")
            if item.get("level") not in LEVELS:
                errors.append(f"{rid}: niveau '{item.get('level')}' inconnu {sorted(LEVELS)}")
            if item.get("status") not in STATUSES:
                errors.append(f"{rid}: statut '{item.get('status')}' inconnu {STATUSES}")
            reqs[rid] = Requirement(rid, item, path)
    return reqs


# --------------------------------------------------------------------------- tests

def _is_excluded(path: Path, repo: Path) -> bool:
    rel = path.relative_to(repo)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return True
    rel_posix = rel.as_posix()
    return any(rel_posix.startswith(sub + "/") for sub in EXCLUDED_SUBPATHS)


def _req_ids_from_mark(node: ast.AST) -> list[str]:
    """Extrait les identifiants de `pytest.mark.req(...)` ou `mark.req(...)`."""
    ids: list[str] = []
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "req":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    ids.append(arg.value)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            ids.extend(_req_ids_from_mark(elt))
    return ids


def _decorator_reqs(decorators: list[ast.expr]) -> list[str]:
    out: list[str] = []
    for dec in decorators:
        out.extend(_req_ids_from_mark(dec))
    return out


def collect_tests(repo: Path, errors: list[str]) -> list[TestCase]:
    tests: list[TestCase] = []
    candidates = set(repo.rglob("test_*.py")) | set(repo.rglob("*_test.py"))
    for path in sorted(candidates):
        if _is_excluded(path, repo):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"{path.relative_to(repo)}: analyse impossible ({exc})")
            continue
        module_reqs: list[str] = []
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "pytestmark" for t in stmt.targets
            ):
                module_reqs.extend(_req_ids_from_mark(stmt.value))
        rel = path.relative_to(repo).as_posix()
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name.startswith("test"):
                tests.append(TestCase(f"{rel}::{stmt.name}", module_reqs + _decorator_reqs(stmt.decorator_list)))
            elif isinstance(stmt, ast.ClassDef) and stmt.name.startswith("Test"):
                class_reqs = module_reqs + _decorator_reqs(stmt.decorator_list)
                for sub in stmt.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name.startswith("test"):
                        tests.append(TestCase(
                            f"{rel}::{stmt.name}::{sub.name}",
                            class_reqs + _decorator_reqs(sub.decorator_list),
                        ))
    return tests


# --------------------------------------------------------------------------- contrôle

def check(repo: Path, max_untraced: int | None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    reqs = load_requirements(repo, errors)
    tests = collect_tests(repo, errors)

    coverage: dict[str, list[str]] = {rid: [] for rid in reqs}
    untraced = 0
    for tc in tests:
        if not tc.reqs:
            untraced += 1
        for rid in tc.reqs:
            if rid in coverage:
                coverage[rid].append(tc.nodeid)
            else:
                errors.append(f"{tc.nodeid}: vise {rid}, qui n'existe pas")

    for rid, req in reqs.items():
        d = req.data
        method = d.get("method")
        if method == "test" and not coverage[rid]:
            errors.append(f"{rid}: méthode 'test' sans aucun test marqué")
        if method in METHODS - {"test"}:
            ev = d.get("evidence")
            if not ev:
                errors.append(f"{rid}: méthode '{method}' sans champ 'evidence'")
            elif not (repo / str(ev)).exists():
                if d.get("status") in ("implemented", "verified"):
                    errors.append(f"{rid}: preuve introuvable '{ev}'")
                else:
                    warnings.append(f"{rid}: preuve pas encore produite '{ev}'")
        if d.get("safety") is True:
            if coverage[rid] and d.get("status") == "draft":
                errors.append(f"{rid}: exigence SAFETY couverte par des tests mais encore en 'draft' (validation opérateur requise)")
            if d.get("status") != "draft" and not d.get("approved_by"):
                errors.append(f"{rid}: exigence SAFETY sans 'approved_by'")

    if max_untraced is not None and untraced > max_untraced:
        errors.append(f"{untraced} tests non tracés pour un plafond de {max_untraced} (cliquet)")

    return {
        "requirements": len(reqs),
        "tests": len(tests),
        "untraced_tests": untraced,
        "coverage": coverage,
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="racine du dépôt (défaut : .)")
    parser.add_argument("--max-untraced", type=int, default=None, help="plafond de tests non tracés")
    parser.add_argument("--report", action="store_true", help="affiche le détail et sort toujours 0")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"trace_check: dépôt introuvable : {repo}", file=sys.stderr)
        return 2
    result = check(repo, args.max_untraced)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Exigences : {result['requirements']} | tests : {result['tests']} | "
              f"tests non tracés : {result['untraced_tests']}")
        if args.report:
            for rid, nodes in sorted(result["coverage"].items()):
                print(f"  {rid:<20} {len(nodes)} test(s)")
        for w in result["warnings"]:
            print(f"AVERTISSEMENT : {w}")
        for e in result["errors"]:
            print(f"ERREUR : {e}", file=sys.stderr)
        if not result["errors"]:
            print("Traçabilité conforme.")
    if args.report:
        return 0
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
