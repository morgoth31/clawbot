"""Tests de contrat de la surface directeur : start_skill, get_task, cancel_task.

Le pont ne simule pas de graphe : la couche ROS est remplacée par un faux directeur qui
enregistre les requêtes reçues, sauf pour le test d'indisponibilité qui utilise la vraie
couche (aucun service sur le domaine 99, donc refus typé).
"""

from __future__ import annotations

import pytest

import bridge_mcp.tools as tools_module
from bridge_mcp import contract, limits
from bridge_mcp.ros_layer import RosLayer

pytestmark = pytest.mark.contract


class FauxDirecteur:
    """Remplace RosLayer : rejoue des réponses et retient les requêtes."""

    def __init__(self, reponses=None):
        self.reponses = list(reponses or [])
        self.recus: list[dict] = []

    def director_command(self, request, timeout=None):
        self.recus.append(request)
        if not self.reponses:
            raise AssertionError(f"appel inattendu au directeur : {request}")
        return self.reponses.pop(0)


def _donnees(result):
    structured = result.structured_content or {}
    return structured.get("result", structured)["data"]


def test_start_skill_transmet_l_intention_et_trace_l_appel(monkeypatch, server, client):
    faux = FauxDirecteur([{"status": "ACCEPTED", "task_id": "t-abc", "skill": "navigate_to",
                           "steps": 1}])
    monkeypatch.setattr(tools_module, "_ROS", faux)

    result = client.call_tool("start_skill", {"skill": "navigate_to",
                                              "args": {"waypoint": "cuisine"},
                                              "justification": "rangement"})

    assert result.is_error is False
    assert _donnees(result)["task_id"] == "t-abc"
    assert faux.recus == [{"op": "start_skill", "skill": "navigate_to",
                           "args": {"waypoint": "cuisine"}}]
    assert any(e.get("event") == "start_skill" and e.get("skill") == "navigate_to"
               for e in server.state.audit)


def test_start_skill_refuse_un_skill_hors_enumeration_sans_appeler_ros(monkeypatch, client):
    faux = FauxDirecteur([])
    monkeypatch.setattr(tools_module, "_ROS", faux)

    result = client.call_tool("start_skill", {"skill": "drive_to_free_xy", "args": {}})

    assert result.is_error is True
    assert result.structured_content["error"]["code"] == "MCP-E-ARG"
    assert result.structured_content["error"]["allowed"] == list(limits.LIMITS["allowed_skills"])
    assert faux.recus == [], "aucun appel ne doit partir pour un skill non déclaré"


def test_busy_is_a_protocol_answer_not_an_error(monkeypatch, client):
    faux = FauxDirecteur([{"status": "BUSY", "task_id": "t-deja", "skill": "grasp_object"}])
    monkeypatch.setattr(tools_module, "_ROS", faux)

    result = client.call_tool("start_skill", {"skill": "navigate_to", "args": {}})

    assert result.is_error is False
    assert _donnees(result)["status"] == "BUSY"
    assert _donnees(result)["task_id"] == "t-deja"


def test_get_task_sert_l_etat_courant(monkeypatch, client):
    faux = FauxDirecteur([{"status": "FOUND", "task": {"task_id": "t-abc", "state": "RUNNING",
                                                       "skill": "navigate_to", "step": 0}}])
    monkeypatch.setattr(tools_module, "_ROS", faux)

    result = client.call_tool("get_task", {})

    assert result.is_error is False
    assert _donnees(result)["task"]["task_id"] == "t-abc"
    assert faux.recus == [{"op": "get_task"}]


def test_get_task_sur_un_identifiant_inconnu_refuse(monkeypatch, client):
    faux = FauxDirecteur([{"status": "UNKNOWN_TASK", "task_id": "t-fantome"}])
    monkeypatch.setattr(tools_module, "_ROS", faux)

    result = client.call_tool("get_task", {"task_id": "t-fantome"})

    assert result.is_error is True
    assert result.structured_content["error"]["code"] == "MCP-E-ARG"
    assert faux.recus == [{"op": "get_task", "task_id": "t-fantome"}]


def test_cancel_task_transmet_le_motif(monkeypatch, client):
    faux = FauxDirecteur([{"status": "CANCELLED", "task_id": "t-abc", "step": 0}])
    monkeypatch.setattr(tools_module, "_ROS", faux)

    result = client.call_tool("cancel_task", {"task_id": "t-abc", "reason": "operateur"})

    assert result.is_error is False
    assert _donnees(result)["status"] == "CANCELLED"
    assert faux.recus == [{"op": "cancel_task", "task_id": "t-abc", "reason": "operateur"}]


def test_cancel_task_refuse_de_s_attribuer_un_motif_de_securite(monkeypatch, client):
    faux = FauxDirecteur([])
    monkeypatch.setattr(tools_module, "_ROS", faux)

    result = client.call_tool("cancel_task", {"task_id": "t-abc", "reason": "safety_stale"})

    assert result.is_error is True
    assert result.structured_content["error"]["code"] == "MCP-E-ARG"
    assert faux.recus == []


def test_director_tools_refusent_proprement_quand_le_directeur_est_absent(monkeypatch, client):
    """Domaine 99 sans directeur : refus typé, jamais une valeur inventée."""
    monkeypatch.setattr(tools_module, "_ROS", RosLayer(domain_id="99", timeout=1.0))

    for outil, arguments in (("start_skill", {"skill": "navigate_to", "args": {}}),
                             ("get_task", {}),
                             ("cancel_task", {"task_id": "t-abc"})):
        result = client.call_tool(outil, arguments)
        assert result.is_error is True, f"{outil} aurait dû refuser"
        assert result.structured_content["error"]["code"] in {"MCP-E-PREREQ", "MCP-E-TIMEOUT"}


def test_un_skill_declare_mais_indisponible_refuse_en_prerequis(monkeypatch, client):
    faux = FauxDirecteur([{"status": "INDISPONIBLE",
                           "reason": "catalogue de waypoints absent (lot 5)"}])
    monkeypatch.setattr(tools_module, "_ROS", faux)

    result = client.call_tool("start_skill", {"skill": "navigate_to", "args": {}})

    assert result.is_error is True
    assert result.structured_content["error"]["code"] == "MCP-E-PREREQ"
    assert "waypoints" in result.structured_content["error"]["message"]


def test_les_trois_outils_sont_dans_le_contrat():
    assert {"start_skill", "get_task", "cancel_task"} <= set(contract.EXPECTED_TOOLS)
    assert "get_task" in contract.READ_ONLY_TOOLS
    assert {"start_skill", "cancel_task"} <= set(contract.MUTATION_TOOLS)
