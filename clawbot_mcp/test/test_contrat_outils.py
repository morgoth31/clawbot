"""Contrat d'outils et descriptions (REQ-MCP-001, REQ-MCP-006)."""
from __future__ import annotations

import pytest

from clawbot_mcp.outils import DESCRIPTIONS, NOMS_OUTILS, OUTILS

pytestmark = [pytest.mark.req("REQ-MCP-001"), pytest.mark.req("REQ-MCP-006")]

ATTENDUS = (
    "get_robot_status", "list_capabilities", "set_capability", "list_skills",
    "start_skill", "start_mission", "get_mission_status", "cancel_mission",
    "get_failure_report", "submit_decision", "stop_robot", "get_snapshot",
)


def test_exactement_douze_outils():
    assert len(OUTILS) == 12
    assert set(OUTILS) == set(ATTENDUS) == set(NOMS_OUTILS)


def test_aucun_outil_en_plus():
    assert sorted(OUTILS) == sorted(ATTENDUS)
    assert len(DESCRIPTIONS) == 12


@pytest.mark.parametrize("nom", ATTENDUS)
def test_descriptions_bornees_et_informatives(nom):
    description = DESCRIPTIONS[nom]
    assert len(description) < 400, f"{nom} : {len(description)} caractères"
    assert "Renvoie" in description or "renvoie" in description, nom
    assert len(description) > 60, nom


def test_serveur_enregistre_les_douze_outils():
    from clawbot_mcp.serveur import Contexte, construire_serveur

    mcp, enregistres = construire_serveur(Contexte(registre={}))
    assert set(enregistres) == set(ATTENDUS)
    assert mcp.name == "clawbot_mcp"
