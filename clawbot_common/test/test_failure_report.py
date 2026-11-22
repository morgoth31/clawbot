"""Schéma du rapport d'échec §6.2 (REQ-ARCH-011)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "clawbot_common"))

from clawbot_common.validation import validate  # noqa: E402

pytestmark = pytest.mark.req("REQ-ARCH-011")

EXEMPLE = {
    "schema": "clawbot.failure_report/1",
    "mission_id": "6f1c",
    "objective": "Va devant la porte et prends une photo",
    "step_index": 1,
    "skill": "navigate_to",
    "params": {"x": 2.0, "y": 0.5, "yaw": 0.0},
    "error_code": "GOAL_UNREACHABLE",
    "error_category": "EXECUTION",
    "message": "Nav2 n'a pas trouvé de chemin",
    "attempts": 1,
    "auto_retries_done": 0,
    "health": {"level": "OK", "active_capabilities": ["base", "lidar", "navigation"],
               "stale_flows": [], "safety_state": "OK", "estop_latched": False,
               "voltage": 11.8},
    "last_events": [],
    "allowed_decisions": ["RETRY_WITH_PARAMS", "REPLACE_REMAINING", "ABORT"],
    "budget": {"escalations_left": 2, "same_step_attempts_left": 1, "time_left_s": 412},
    "stamp": "2026-11-22T14:03:11+01:00",
}


def test_l_exemple_du_referentiel_est_valide():
    assert validate(EXEMPLE, "failure_report") == []


def test_un_rapport_sans_error_code_est_refuse():
    sans_code = dict(EXEMPLE)
    sans_code.pop("error_code")
    assert validate(sans_code, "failure_report"), "error_code est obligatoire"


def test_une_decision_hors_table_est_refusee():
    faux = dict(EXEMPLE, allowed_decisions=["FAIRE_LE_CAFE"])
    assert validate(faux, "failure_report")


def test_le_schema_est_du_draft_2020_12():
    from clawbot_common.validation import schema_path

    document = json.loads(schema_path("failure_report").read_text(encoding="utf-8"))
    assert document["$schema"].endswith("2020-12/schema")
