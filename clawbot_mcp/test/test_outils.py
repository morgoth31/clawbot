"""Outils : nominal, exécutif absent, entrée invalide (REQ-MCP-003, REQ-MCP-005)."""
from __future__ import annotations

import time

import pytest

from clawbot_executive.registre import Definition
from clawbot_mcp import outils
from clawbot_mcp.serveur import Contexte

pytestmark = [pytest.mark.req("REQ-MCP-003"), pytest.mark.req("REQ-MCP-005")]


class FauxFutur:
    def __init__(self, resultat=None, prete=True):
        self._resultat = resultat
        self._prete = prete

    def done(self) -> bool:
        return self._prete

    def result(self):
        return self._resultat

    def add_done_callback(self, rappel):
        self._rappel = rappel
        return self


class FauxClient:
    """Client de service factice : répond, ou reste muet (exécutif absent)."""

    def __init__(self, resultat=None, pret=True):
        self.resultat = resultat
        self.pret = pret
        self.requetes = []

    def wait_for_service(self, timeout_sec=None):
        return self.pret

    def call_async(self, requete):
        self.requetes.append(requete)
        return FauxFutur(self.resultat, prete=self.pret)


class FauxResultatCapacites:
    capabilities_json = '[{"name": "base", "state": "ACTIVE"}]'


def registre():
    return {"wait": Definition(nom="wait", description="attendre",
                               params_schema={"type": "object"}, requires=[],
                               timeout_s=5.0, bornes={})}


def contexte(clients=None, editeur=None):
    return Contexte(registre=registre(), clients=clients or {}, editeur=editeur)


def test_list_skills_expose_schema_et_capacites():
    reponse = outils.list_skills(contexte())
    assert reponse["ok"] and reponse["skills"][0]["name"] == "wait"
    assert reponse["skills"][0]["params_schema"] == {"type": "object"}


def test_executif_absent_rend_un_code():
    """Aucun client : la réponse porte ok=false et un code de §6.1, pas une exception."""
    reponse = outils.list_capabilities(contexte())
    assert reponse["ok"] is False
    assert reponse["error_code"] == "TIMEOUT"
    assert reponse["error_category"] == "EXECUTION"


def test_entree_invalide_rend_invalid_params():
    reponse = outils.start_mission(contexte(), "test", [])
    assert reponse["error_code"] == "INVALID_PARAMS"
    reponse = outils.start_mission(contexte(), "test", [{"skill": "inconnu"}])
    assert reponse["error_code"] == "UNKNOWN_SKILL"
    reponse = outils.submit_decision(contexte(), "m", "ABORT", None, "")
    assert reponse["error_code"] == "INVALID_PARAMS"


def test_exception_interne_capturee():
    from clawbot_mcp.serveur import construire_serveur

    mcp, enregistres = construire_serveur(contexte())
    sortie = enregistres["list_capabilities"]()
    charge = __import__("json").loads(sortie)
    assert charge["ok"] is False and charge["error_code"]


def test_start_mission_rend_la_main(monkeypatch):
    """REQ-MCP-003 : moins de 1 s, avec un mission_id."""
    from clawbot_interfaces.action import ExecuteMission

    class FauxHandle:
        goal_id = type("G", (), {"uuid": b"0" * 16})()

        accepted = True

        def get_result_async(self):
            return FauxFutur(None, prete=False)

    class FauxActionClient:
        def wait_for_server(self, timeout_sec=None):
            return True

        def send_goal_async(self, goal):
            return FauxFutur(FauxHandle())

    contexte_ = contexte()
    contexte_.node = type("N", (), {"actions": {"mission": FauxActionClient()}})()
    debut = time.monotonic()
    reponse = outils.start_mission(contexte_, "test", [{"skill": "wait", "params": {}}])
    ecoule = time.monotonic() - debut
    assert reponse["ok"], reponse
    assert reponse["mission_id"]
    assert ecoule < 1.0, f"{ecoule * 1000:.0f} ms"


def test_start_skill_rend_la_main(monkeypatch):
    from clawbot_mcp import outils as module

    contexte_ = contexte()
    contexte_.lancer_mission = lambda objective, etapes, duree: outils.ok(mission_id="m-1")
    reponse = module.start_skill(contexte_, "wait", {"seconds": 1})
    assert reponse == {"ok": True, "mission_id": "m-1"}
