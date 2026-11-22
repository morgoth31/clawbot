"""Autorisation sudo du gestionnaire : bornée, nominative, sans joker (REQ-CAPA-001)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
GENERATEUR = RACINE / "scripts" / "gen_capability_auth.py"
FICHIER = RACINE / "deploy" / "sudoers" / "clawbot-capabilities"

pytestmark = pytest.mark.req("REQ-CAPA-001")


def _manifeste():
    from clawbot_capabilities.manifeste import charger

    return charger(RACINE / "clawbot_capabilities" / "config" / "capabilities.yaml")


def test_fichier_versionne_est_a_jour():
    sortie = subprocess.run([sys.executable, str(GENERATEUR), "--verifier"],
                            capture_output=True, text=True, timeout=60)
    assert sortie.returncode == 0, sortie.stderr


def test_chaque_unite_geree_est_autorisee_en_start_et_stop():
    contenu = FICHIER.read_text(encoding="utf-8")
    for capacite in _manifeste().values():
        if not capacite.managed:
            continue
        for unite in capacite.units:
            assert f"start {unite}" in contenu, unite
            assert f"stop {unite}" in contenu, unite


def test_aucun_joker_sur_start_ou_stop():
    for ligne in FICHIER.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("#") or not ligne.strip():
            continue
        if " start " in ligne or " stop " in ligne:
            assert "*" not in ligne, ligne


def test_capacite_non_geree_absente():
    contenu = FICHIER.read_text(encoding="utf-8")
    for capacite in _manifeste().values():
        if capacite.managed:
            continue
        for unite in capacite.units:
            assert f"start {unite}" not in contenu, unite


def test_utilisateur_nominatif_et_nopasswd():
    for ligne in FICHIER.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("#") or not ligne.strip():
            continue
        assert ligne.startswith("jetson ALL=(root) NOPASSWD: "), ligne


def test_generation_reproductible(tmp_path):
    """Deux exécutions donnent le même contenu : le fichier peut être comparé."""
    premier = subprocess.run([sys.executable, str(GENERATEUR), "--stdout"],
                             capture_output=True, text=True, check=True)
    second = subprocess.run([sys.executable, str(GENERATEUR), "--stdout"],
                            capture_output=True, text=True, check=True)
    assert premier.stdout == second.stdout == FICHIER.read_text(encoding="utf-8")
