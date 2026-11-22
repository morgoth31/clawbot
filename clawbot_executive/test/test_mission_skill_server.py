"""REQ-EXEC-021 — sans serveur de skills, aucune mission n'est acceptée.

Le 2026-11-22, `clawbot-skill-server` a planté en boucle : `Requires=` a arrêté
`clawbot-mission-executive`, qui n'est jamais revenu, et rien ne signalait qu'une action
de l'exécutif manquait. Ces tests figent la règle : un goal de mission est refusé tant que
`/clawbot/execute_skill` est absent, et accepté dès qu'il revient — sans relance
automatique ni attente bloquante.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

if os.environ.get("ROS_DOMAIN_ID") != "98":
    pytest.skip("tests rclpy : domaine 98 requis", allow_module_level=True)

import rclpy  # noqa: E402
from rclpy.action import GoalResponse  # noqa: E402

from clawbot_executive.mission_node import MissionExecutive  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
REGISTRE = RACINE / "clawbot_executive" / "config" / "skills.yaml"

pytestmark = pytest.mark.req("REQ-EXEC-021")


class ClientSkillsFactice:
    """Remplace `ActionClient` : seule la présence importe ici."""

    def __init__(self, pret: bool):
        self._pret = pret

    def server_is_ready(self) -> bool:
        return self._pret

    def wait_for_server(self, timeout_sec: float = 0.0) -> bool:  # noqa: ARG002
        return self._pret


@pytest.fixture(scope="module", autouse=True)
def contexte():
    """Un seul contexte rclpy pour tout le fichier (pas de shutdown entre fichiers)."""
    if not rclpy.ok():
        rclpy.init()
    yield


def _noeud(pret: bool) -> MissionExecutive:
    return MissionExecutive(registre=REGISTRE, client_skills=ClientSkillsFactice(pret))


def test_mission_refusee_sans_serveur_de_skills():
    noeud = _noeud(False)
    try:
        assert noeud._sur_goal(None) == GoalResponse.REJECT  # noqa: SLF001
        assert noeud.dernier_refus == "SKILL_SERVER_UNAVAILABLE"
    finally:
        noeud.destroy_node()


def test_mission_acceptee_des_que_le_serveur_revient():
    noeud = _noeud(True)
    try:
        assert noeud._sur_goal(None) == GoalResponse.ACCEPT  # noqa: SLF001
        assert noeud.dernier_refus == ""
    finally:
        noeud.destroy_node()


def test_le_refus_suit_l_etat_du_serveur_en_cours_de_vie():
    """Pas de relance automatique : c'est chaque goal qui revérifie."""
    noeud = _noeud(True)
    try:
        assert noeud._sur_goal(None) == GoalResponse.ACCEPT  # noqa: SLF001
        noeud.cli_skills = ClientSkillsFactice(False)
        assert noeud._sur_goal(None) == GoalResponse.REJECT  # noqa: SLF001
        assert noeud.dernier_refus == "SKILL_SERVER_UNAVAILABLE"
        noeud.cli_skills = ClientSkillsFactice(True)
        assert noeud._sur_goal(None) == GoalResponse.ACCEPT  # noqa: SLF001
        assert noeud.dernier_refus == ""
    finally:
        noeud.destroy_node()
