"""stop_robot ne dépend de personne (REQ-MCP-004)."""
from __future__ import annotations

import pytest

from clawbot_mcp import outils
from clawbot_mcp.serveur import Contexte

pytestmark = pytest.mark.req("REQ-MCP-004")


class FauxEditeur:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


def test_stop_robot_publie_estop_true_sans_executif():
    editeur = FauxEditeur()
    contexte = Contexte(registre={}, clients={}, editeur=editeur)   # exécutif absent
    reponse = outils.stop_robot(contexte, "test")
    assert reponse["ok"] is True
    assert len(editeur.messages) == 1
    assert editeur.messages[0].data is True


def test_stop_robot_sans_editeur_rend_un_code():
    reponse = outils.stop_robot(Contexte(registre={}, clients={}, editeur=None), "test")
    assert reponse["ok"] is False and reponse["error_code"]
