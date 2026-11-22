"""Tests du cadre de développement et de la suite verte (P00).

Ces tests vérifient le cadre lui-même, pas le robot :
  - la garde de domaine DDS de ``scripts/check.sh`` ;
  - la non-collecte pytest des scripts manuels ;
  - la présence du référentiel d'architecture ;
  - la composition des étapes de ``check.sh --self-test``.

Ils sont volontairement écrits avant le code : au premier lancement, tout
échoue parce que ``scripts/check.sh`` et ``docs/architecture/cible.md``
n'existent pas encore.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK = REPO_ROOT / "scripts" / "check.sh"
REFERENTIEL = REPO_ROOT / "docs" / "architecture" / "cible.md"

# Variables qui fausseraient un sous-processus de test.
_STRIPPED = ("VIRTUAL_ENV", "PYTHONHOME", "PYTEST_CURRENT_TEST", "PYTEST_XDIST_WORKER")


def _env(**extra: str) -> dict[str, str]:
    """Environnement propre pour lancer un sous-processus de test."""
    env = {k: v for k, v in os.environ.items() if k not in _STRIPPED}
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    env.update(extra)
    return env


def _run(cmd: list[str], env: dict[str, str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=timeout
    )


# ── REQ-TEST-002 : garde de domaine DDS ──────────────────────────────────────

@pytest.mark.req("REQ-TEST-002")
def test_check_refuse_domaine_28():
    """Le domaine de production (28) est refusé, avec 28 dans le message."""
    assert CHECK.is_file(), "scripts/check.sh doit exister"
    proc = _run([str(CHECK), "--self-test"], _env(ROS_DOMAIN_ID="28"), timeout=120)

    assert proc.returncode != 0, "check.sh doit refuser de tourner en domaine 28"
    assert "28" in proc.stderr, f"message explicite attendu sur stderr, obtenu : {proc.stderr!r}"


@pytest.mark.req("REQ-TEST-002")
def test_check_domaine_par_defaut():
    """Sans ROS_DOMAIN_ID, check.sh impose 98 et le dit."""
    env = _env()
    env.pop("ROS_DOMAIN_ID", None)
    proc = _run([str(CHECK), "--self-test"], env, timeout=120)

    assert proc.returncode == 0, f"sortie {proc.returncode} : {proc.stderr[-2000:]}"
    assert "ROS_DOMAIN_ID=98" in proc.stdout + proc.stderr, (
        f"défaut attendu ROS_DOMAIN_ID=98, sortie : {proc.stdout + proc.stderr!r}"
    )


# ── REQ-TEST-004 : les scripts manuels ne sont pas collectés ─────────────────

@pytest.mark.req("REQ-TEST-004")
def test_scripts_manuels_non_collectes():
    """`pytest --collect-only -q` ne doit lister aucun fichier de tests/manual/."""
    proc = _run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        _env(ROS_DOMAIN_ID="98", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"),
        timeout=300,
    )

    assert proc.returncode == 0, f"collecte en erreur :\n{proc.stdout[-3000:]}"
    offensants = [
        ligne for ligne in proc.stdout.splitlines() if "tests/manual/" in ligne
    ]
    assert not offensants, "collectés par erreur :\n" + "\n".join(offensants)


# ── REQ-ARCH-001 : référentiel versionné ─────────────────────────────────────

@pytest.mark.req("REQ-ARCH-001")
def test_referentiel_present():
    """Le référentiel est présent et commence par son titre."""
    assert REFERENTIEL.is_file(), "docs/architecture/cible.md manquant"
    premiere = REFERENTIEL.read_text(encoding="utf-8").splitlines()[0]
    assert premiere.startswith("# Architecture cible Clawbot X3"), (
        f"titre inattendu : {premiere!r}"
    )


# ── REQ-TEST-001/003/005 : la vérification complète annonce ses étapes ───────

@pytest.mark.req("REQ-TEST-001", "REQ-TEST-003", "REQ-TEST-005")
def test_check_complet_self_test():
    """`check.sh --self-test` sort 0 et annonce lint, unit, trace, doublons."""
    assert CHECK.is_file(), "scripts/check.sh doit exister"
    proc = _run([str(CHECK), "--self-test"], _env(ROS_DOMAIN_ID="98"), timeout=120)

    assert proc.returncode == 0, f"sortie {proc.returncode} : {proc.stderr[-2000:]}"
    sortie = (proc.stdout + proc.stderr).lower()
    for etape in ("lint", "unit", "trace", "doublons"):
        assert etape in sortie, f"étape '{etape}' absente de l'annonce :\n{sortie}"
