"""Rapport d'échec conforme au schéma §6.2 (REQ-EXEC-008)."""
from __future__ import annotations

import pytest

from clawbot_common.validation import validate

pytestmark = pytest.mark.req("REQ-EXEC-008")


def rapport(code: str) -> dict:
    from clawbot_common.errors import rapport_echec

    return rapport_echec(
        mission_id="m-1", objective="aller au salon", step_index=0, skill="move_relative",
        params={"dx_m": 0.5}, error_code=code, message="test",
        health={"level": "OK", "active_capabilities": ["base", "lidar"], "stale_flows": [],
                "safety_state": "OK", "estop_latched": False, "voltage": 11.9},
        budget={"escalations_left": 2, "same_step_attempts_left": 1, "time_left_s": 120.0},
    )


@pytest.mark.parametrize("code", ["INVALID_PARAMS", "CAPABILITY_INACTIVE", "SAFETY_HOLD",
                                  "SENSOR_STALE", "ESTOP_LATCHED", "TIMEOUT", "UNKNOWN_SKILL"])
def test_le_rapport_valide_le_schema(code):
    document = rapport(code)
    assert validate(document, "failure_report") == []
    assert document["error_code"] == code
    assert document["error_category"]  # jamais vide


def test_les_decisions_viennent_de_la_table():
    from clawbot_common.errors import allowed_decisions, rapport_echec

    document = rapport_echec(
        mission_id="m-1", objective="", step_index=0, skill="rotate", params={},
        error_code="ESTOP_LATCHED", message="e-stop",
        health={"level": "ERROR", "active_capabilities": [], "stale_flows": [],
                "safety_state": "ESTOP_LATCHED", "estop_latched": True, "voltage": 11.9},
        budget={"escalations_left": 0, "same_step_attempts_left": 0, "time_left_s": 0.0},
    )
    assert tuple(document["allowed_decisions"]) == allowed_decisions("ESTOP_LATCHED")


def test_code_inconnu_refuse():
    with pytest.raises(KeyError):
        rapport("PAS_UN_CODE")
