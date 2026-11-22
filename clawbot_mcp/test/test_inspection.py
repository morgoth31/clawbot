"""Aucun accès direct aux actionneurs (REQ-MCP-002)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.req("REQ-MCP-002")

PAQUET = Path(__file__).resolve().parents[1] / "clawbot_mcp"
SOURCES = {f.name: f.read_text(encoding="utf-8") for f in PAQUET.glob("*.py")}


def test_aucune_publication_de_vitesse_ni_de_servo():
    for nom, source in SOURCES.items():
        assert "Twist(" not in source, f"{nom} construit un Twist"
        assert "Int32MultiArray" not in source, f"{nom} parle de servo"
        assert "/cmd_vel" not in source, f"{nom} touche /cmd_vel"


def test_aucun_rearmement_d_estop():
    for nom, source in SOURCES.items():
        assert "reset_estop" not in source, f"{nom} pourrait réarmer l'e-stop"
        assert "Trigger" not in source, f"{nom} crée un client Trigger"


def test_aucune_modification_de_parametre():
    for nom, source in SOURCES.items():
        assert "set_parameters" not in source, nom
        assert "Parameter" not in source, nom


def test_aucune_commande_shell():
    for nom, source in SOURCES.items():
        arbre = ast.parse(source)
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.Import, ast.ImportFrom)):
                modules = ([a.name for a in noeud.names] if isinstance(noeud, ast.Import)
                           else [noeud.module or ""])
                for module in modules:
                    assert module.split(".")[0] not in ("subprocess", "shlex", "pty"), \
                        f"{nom} importe {module}"
            if isinstance(noeud, ast.Attribute) and noeud.attr in ("system", "popen", "spawn"):
                if isinstance(noeud.value, ast.Name) and noeud.value.id == "os":
                    raise AssertionError(f"{nom} appelle os.{noeud.attr}")


def test_seul_editeur_est_le_verrou_d_estop():
    source = SOURCES["serveur.py"]
    publications = [ligne for ligne in source.splitlines() if "create_publisher(" in ligne]
    assert len(publications) == 1, publications
    assert "/safety/estop" in publications[0]
