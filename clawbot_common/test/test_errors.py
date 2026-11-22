"""Table d'erreurs unique et son export JSON (REQ-ARCH-011/012)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "clawbot_common"))

from clawbot_common import errors  # noqa: E402

DECISIONS_AUTORISEES = {"RETRY_STEP", "RETRY_WITH_PARAMS", "SKIP_STEP",
                        "REPLACE_REMAINING", "ABORT"}
CATEGORIES = {"PRECONDITION", "SENSOR", "SAFETY", "EXECUTION", "HARDWARE",
              "INTERFACE", "INTERNAL"}

# Le §6.1 du référentiel, recopié : 19 codes, catégorie, relance, décisions.
ATTENDUS = {
    "CAPABILITY_INACTIVE": ("PRECONDITION", 0, {"RETRY_STEP", "REPLACE_REMAINING", "ABORT"}),
    "CAPABILITY_CONFLICT": ("PRECONDITION", 0, {"REPLACE_REMAINING", "ABORT"}),
    "ARM_NOT_AT_REST": ("PRECONDITION", 0, {"REPLACE_REMAINING", "ABORT"}),
    "MAP_MISSING": ("PRECONDITION", 0, {"REPLACE_REMAINING", "ABORT"}),
    "SENSOR_STALE": ("SENSOR", 1, {"RETRY_STEP", "REPLACE_REMAINING", "ABORT"}),
    "DEPTH_UNAVAILABLE": ("SENSOR", 0, {"REPLACE_REMAINING", "ABORT"}),
    "SAFETY_HOLD": ("SAFETY", 0, {"RETRY_STEP", "REPLACE_REMAINING", "ABORT"}),
    "OBSTACLE_TOO_CLOSE": ("SAFETY", 0, {"REPLACE_REMAINING", "ABORT"}),
    "ESTOP_LATCHED": ("SAFETY", 0, {"ABORT"}),
    "LOW_VOLTAGE": ("SAFETY", 0, {"ABORT"}),
    "TIMEOUT": ("EXECUTION", 1, {"RETRY_WITH_PARAMS", "REPLACE_REMAINING", "ABORT"}),
    "GOAL_UNREACHABLE": ("EXECUTION", 0, {"RETRY_WITH_PARAMS", "REPLACE_REMAINING", "ABORT"}),
    "PLANNING_FAILED": ("EXECUTION", 1, {"RETRY_WITH_PARAMS", "REPLACE_REMAINING", "ABORT"}),
    "GRASP_FAILED": ("EXECUTION", 0, {"RETRY_WITH_PARAMS", "SKIP_STEP", "ABORT"}),
    "SERIAL_LOST": ("HARDWARE", 0, {"ABORT"}),
    "SERVO_NO_FEEDBACK": ("HARDWARE", 0, {"ABORT"}),
    "INVALID_PARAMS": ("INTERFACE", 0, {"RETRY_WITH_PARAMS", "ABORT"}),
    "UNKNOWN_SKILL": ("INTERFACE", 0, {"REPLACE_REMAINING", "ABORT"}),
    "UNHANDLED_EXCEPTION": ("INTERNAL", 0, {"ABORT"}),
}


@pytest.mark.req("REQ-ARCH-012")
def test_la_table_couvre_exactement_le_referentiel():
    assert set(errors.CODES) == set(ATTENDUS), "un code manque ou un code est en trop"


@pytest.mark.parametrize("code", sorted(ATTENDUS))
@pytest.mark.req("REQ-ARCH-012")
def test_categorie_relance_et_decisions(code):
    categorie, relance, decisions = ATTENDUS[code]
    assert errors.category(code) == categorie
    essais, delai = errors.auto_retry(code)
    assert essais == relance, f"{code}: relance attendue {relance}"
    if relance:
        assert 0 < delai <= 5.0, f"{code}: un code relancé doit porter un délai"
    assert set(errors.allowed_decisions(code)) == decisions, code


@pytest.mark.parametrize("code", sorted(ATTENDUS))
@pytest.mark.req("REQ-ARCH-012")
def test_categorie_dans_l_ensemble(code):
    assert errors.category(code) in CATEGORIES


@pytest.mark.parametrize("code", sorted(ATTENDUS))
@pytest.mark.req("REQ-ARCH-012")
def test_decisions_non_vides_et_bornees(code):
    decisions = errors.allowed_decisions(code)
    assert decisions, f"{code}: aucune décision autorisée"
    assert set(decisions) <= DECISIONS_AUTORISEES


@pytest.mark.req("REQ-ARCH-011")
def test_codes_uniques_et_immuables():
    assert len(errors.CODES) == len(set(errors.CODES))
    with pytest.raises(TypeError):
        errors.CODES["NOUVEAU"] = {}          # MappingProxyType : immuable


@pytest.mark.req("REQ-ARCH-011")
def test_errors_json_egale_le_module():
    """Le fichier versionné et le module disent exactement la même chose (REQ-ARCH-011)."""
    chemin = RACINE / "share" / "clawbot_common" / "errors.json"
    assert chemin.is_file(), f"export JSON absent : {chemin}"
    document = json.loads(chemin.read_text(encoding="utf-8"))
    assert document == errors.as_json()
    assert document["schema"] == "clawbot.errors/1"
    assert set(document["codes"]) == set(ATTENDUS)


@pytest.mark.req("REQ-ARCH-011")
def test_code_inconnu_leve():
    with pytest.raises(KeyError):
        errors.category("PAS_UN_CODE")
