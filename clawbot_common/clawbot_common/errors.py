"""Table d'erreurs unique du référentiel §6.1 (REQ-ARCH-011, REQ-ARCH-012).

Codée une seule fois ici, exportée en JSON par `share/clawbot_common/errors.json`
(fichier versionné, tenu égal au module par un test). Chaque code porte sa
catégorie, sa règle de relance automatique et les décisions que le LLM a le droit
de demander : un code sans liste laisserait passer n'importe quelle décision.
"""
from __future__ import annotations

import time

from dataclasses import dataclass
from types import MappingProxyType

DECISIONS = ("RETRY_STEP", "RETRY_WITH_PARAMS", "SKIP_STEP", "REPLACE_REMAINING", "ABORT")
CATEGORIES = ("PRECONDITION", "SENSOR", "SAFETY", "EXECUTION", "HARDWARE",
              "INTERFACE", "INTERNAL")
SCHEMA = "clawbot.errors/1"


@dataclass(frozen=True)
class ErrorSpec:
    code: str
    category: str
    auto_retry: int          # 0 ou 1 relance automatique par l'exécutif
    retry_delay_s: float     # délai avant cette relance (0 si aucune)
    decisions: tuple[str, ...]
    operator_alert: bool = False   # prévenir l'opérateur


def _spec(code, category, retries, decisions, delay=0.0, alerte=False):
    return ErrorSpec(code=code, category=category, auto_retry=retries,
                     retry_delay_s=delay if retries else 0.0,
                     decisions=tuple(decisions), operator_alert=alerte)


_TABLE = (
    _spec("CAPABILITY_INACTIVE", "PRECONDITION", 0,
          ["RETRY_STEP", "REPLACE_REMAINING", "ABORT"]),
    _spec("CAPABILITY_CONFLICT", "PRECONDITION", 0, ["REPLACE_REMAINING", "ABORT"]),
    _spec("ARM_NOT_AT_REST", "PRECONDITION", 0, ["REPLACE_REMAINING", "ABORT"]),
    _spec("MAP_MISSING", "PRECONDITION", 0, ["REPLACE_REMAINING", "ABORT"]),
    _spec("SKILL_SERVER_UNAVAILABLE", "PRECONDITION", 0, ["RETRY_STEP", "ABORT"]),
    _spec("SENSOR_STALE", "SENSOR", 1, ["RETRY_STEP", "REPLACE_REMAINING", "ABORT"], delay=2.0),
    _spec("DEPTH_UNAVAILABLE", "SENSOR", 0, ["REPLACE_REMAINING", "ABORT"]),
    _spec("SAFETY_HOLD", "SAFETY", 0, ["RETRY_STEP", "REPLACE_REMAINING", "ABORT"]),
    _spec("OBSTACLE_TOO_CLOSE", "SAFETY", 0, ["REPLACE_REMAINING", "ABORT"]),
    _spec("ESTOP_LATCHED", "SAFETY", 0, ["ABORT"], alerte=True),
    _spec("LOW_VOLTAGE", "SAFETY", 0, ["ABORT"], alerte=True),
    _spec("TIMEOUT", "EXECUTION", 1,
          ["RETRY_WITH_PARAMS", "REPLACE_REMAINING", "ABORT"], delay=0.5),
    _spec("GOAL_UNREACHABLE", "EXECUTION", 0,
          ["RETRY_WITH_PARAMS", "REPLACE_REMAINING", "ABORT"]),
    _spec("PLANNING_FAILED", "EXECUTION", 1,
          ["RETRY_WITH_PARAMS", "REPLACE_REMAINING", "ABORT"], delay=0.5),
    _spec("GRASP_FAILED", "EXECUTION", 0, ["RETRY_WITH_PARAMS", "SKIP_STEP", "ABORT"]),
    _spec("SERIAL_LOST", "HARDWARE", 0, ["ABORT"], alerte=True),
    _spec("SERVO_NO_FEEDBACK", "HARDWARE", 0, ["ABORT"], alerte=True),
    _spec("INVALID_PARAMS", "INTERFACE", 0, ["RETRY_WITH_PARAMS", "ABORT"]),
    _spec("UNKNOWN_SKILL", "INTERFACE", 0, ["REPLACE_REMAINING", "ABORT"]),
    _spec("UNHANDLED_EXCEPTION", "INTERNAL", 0, ["ABORT"]),
)

CODES = MappingProxyType({spec.code: spec for spec in _TABLE})


def _spec_de(code: str) -> ErrorSpec:
    return CODES[code]          # KeyError explicite si le code n'existe pas


def category(code: str) -> str:
    return _spec_de(code).category


def auto_retry(code: str) -> tuple[int, float]:
    """Nombre de relances automatiques et délai avant chacune."""
    spec = _spec_de(code)
    return spec.auto_retry, spec.retry_delay_s


def allowed_decisions(code: str) -> tuple[str, ...]:
    return _spec_de(code).decisions


def operator_alert(code: str) -> bool:
    return _spec_de(code).operator_alert


def as_json() -> dict:
    """Forme publiée dans share/clawbot_common/errors.json."""
    return {
        "schema": SCHEMA,
        "codes": {
            code: {
                "category": spec.category,
                "auto_retry": spec.auto_retry,
                "retry_delay_s": spec.retry_delay_s,
                "decisions": list(spec.decisions),
                "operator_alert": spec.operator_alert,
            }
            for code, spec in CODES.items()
        },
    }


def rapport_echec(*, mission_id: str, objective: str, step_index: int, skill: str,
                  params: dict | None, error_code: str, message: str,
                  health: dict, budget: dict, attempts: int = 1,
                  auto_retries_done: int = 0, last_events: list | None = None,
                  stamp: str | None = None) -> dict:
    """Rapport d'échec conforme au schéma §6.2 (`failure_report.schema.json`).

    Construit à partir de la table d'erreurs : la catégorie et les décisions
    autorisées ne sont jamais recopiées à la main, elles découlent du code.
    """
    spec = _spec_de(error_code)                 # lève KeyError si le code est inconnu
    document = {
        "schema": "clawbot.failure_report/1",
        "mission_id": mission_id,
        "objective": objective,
        "step_index": int(step_index),
        "skill": skill,
        "error_code": error_code,
        "error_category": spec.category,
        "message": message,
        "attempts": int(attempts),
        "auto_retries_done": int(auto_retries_done),
        "health": health,
        "allowed_decisions": list(spec.decisions),
        "budget": budget,
        "stamp": stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z") or "1970-01-01T00:00:00Z",
    }
    if params is not None:
        document["params"] = params
    if last_events:
        document["last_events"] = last_events
    return document
