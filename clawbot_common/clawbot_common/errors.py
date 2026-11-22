"""Table d'erreurs unique du référentiel §6.1 (REQ-ARCH-011, REQ-ARCH-012).

Codée une seule fois ici, exportée en JSON par `share/clawbot_common/errors.json`
(fichier versionné, tenu égal au module par un test). Chaque code porte sa
catégorie, sa règle de relance automatique et les décisions que le LLM a le droit
de demander : un code sans liste laisserait passer n'importe quelle décision.
"""
from __future__ import annotations

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
