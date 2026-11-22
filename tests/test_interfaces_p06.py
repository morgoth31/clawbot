"""Les huit interfaces du référentiel §3 existent avec les bons champs (REQ-ARCH-010)."""
from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.req("REQ-ARCH-010")

# Table recopiée du §3 : nom du type -> {champ: type ROS}
ACTIONS = {
    "ExecuteSkill": {
        "goal": {"mission_id": "string", "skill": "string", "params_json": "string",
                 "timeout_s": "float"},
        "result": {"outcome": "uint8", "error_code": "string", "error_category": "string",
                   "message": "string", "result_json": "string",
                   "failure_report_json": "string"},
        "feedback": {"phase": "string", "progress": "float", "detail_json": "string"},
    },
    "ExecuteMission": {
        "goal": {"mission_id": "string", "objective": "string", "steps_json": "string",
                 "max_escalations": "uint8", "max_duration_s": "float"},
        "result": {"outcome": "uint8", "mission_id": "string", "state": "string",
                   "failure_report_json": "string", "summary_json": "string"},
        "feedback": {"step_index": "uint16", "step_count": "uint16", "state": "string",
                     "current_skill": "string", "progress": "float"},
    },
}

SERVICES = {
    "ListCapabilities": {
        "request": {},
        "response": {"capabilities_json": "string"},
    },
    "SetCapability": {
        "request": {"name": "string", "active": "boolean", "timeout_s": "float"},
        "response": {"success": "boolean", "state": "string", "message": "string"},
    },
    "GetMissionReport": {
        "request": {"mission_id": "string"},
        "response": {"found": "boolean", "report_json": "string"},
    },
    "SubmitDecision": {
        "request": {"mission_id": "string", "decision": "string", "params_json": "string",
                    "rationale": "string"},
        "response": {"accepted": "boolean", "message": "string", "escalations_left": "uint8"},
    },
}

MESSAGES = {
    "RobotHealth": {"stamp": "builtin_interfaces/Time", "level": "uint8",
                    "active_capabilities": "sequence<string>", "stale_flows": "sequence<string>",
                    "safety_state": "string", "estop_latched": "boolean",
                    "voltage": "float", "detail_json": "string"},
    "MissionEvent": {"stamp": "builtin_interfaces/Time", "mission_id": "string",
                     "event": "string", "detail_json": "string"},
}


def _classe(paquet: str, nom: str):
    """Le type généré est un attribut du paquet (`clawbot_interfaces.action`)."""
    return getattr(importlib.import_module(f"clawbot_interfaces.{paquet}"), nom)


@pytest.mark.parametrize("nom", sorted(ACTIONS))
def test_action_champs(nom):
    classe = _classe("action", nom)
    for partie, champs in ACTIONS[nom].items():
        objet = getattr(classe, partie.capitalize())
        assert objet.get_fields_and_field_types() == champs, f"{nom}.{partie}"


@pytest.mark.parametrize("nom", sorted(SERVICES))
def test_service_champs(nom):
    classe = _classe("srv", nom)
    assert classe.Request.get_fields_and_field_types() == SERVICES[nom]["request"], nom
    assert classe.Response.get_fields_and_field_types() == SERVICES[nom]["response"], nom


@pytest.mark.parametrize("nom", sorted(MESSAGES))
def test_message_champs(nom):
    assert _classe("msg", nom).get_fields_and_field_types() == MESSAGES[nom], nom


@pytest.mark.req("REQ-ARCH-010")
def test_constantes_d_outcome():
    """Les constantes du §3 valent 0 à 3 et portent les mêmes noms partout."""
    for nom in ("ExecuteSkill", "ExecuteMission"):
        resultat = _classe("action", nom).Result
        assert (resultat.OUTCOME_SUCCEEDED, resultat.OUTCOME_FAILED,
                resultat.OUTCOME_CANCELED, resultat.OUTCOME_REJECTED) == (0, 1, 2, 3)
