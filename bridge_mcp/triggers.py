"""Moteur de déclenchement de S1 (exigences TRG-01 à TRG-24).

Le jeu de déclencheurs est **clos** : `TRIGGERS` décrit les 14 règles du §3.1 de la
spécification, et aucune autre ne peut être évaluée. Le moteur ne lit aucune horloge globale :
il reçoit l'instant courant, ce qui rend la temporisation testable au pas près.

Deux valeurs de seuil proviennent de décisions encore à l'état de proposition (D-06 : tension
basse ; D-07 : disque libre). Elles sont marquées `decision_ref` et reprises telles quelles dans
le contexte transmis, afin qu'aucune valeur provisoire ne soit présentée comme validée.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from bridge_mcp.observations import Observation, TopicObs
from bridge_mcp.state import BridgeState, Incident

COOLDOWN_S = 60.0
RATE_LIMIT_PER_HOUR = 6
RATE_WINDOW_S = 3600.0
WATCHDOG_WINDOW_S = 30.0
TOOL_FAILURE_THRESHOLD = 3
TOOL_FAILURE_WINDOW_S = 60.0
THERMAL_PASSIVE_C = 70.0
TF_MAX_AGE_S = 1.0
SLOW_RATE_RATIO = 0.5

#: Cadres TF dont l'absence est un prérequis connu sur ce robot (contrainte C-02) : elle est
#: déclarée dans `unavailable` du contexte, pas traitée comme un déclencheur.
REQUIRED_TF_FRAMES: tuple[str, ...] = ()


@dataclass(frozen=True)
class TriggerSpec:
    """Description d'un déclencheur, telle qu'écrite au §3.1 de la spécification."""

    trigger_id: str
    rule: str
    severity: int
    debounce_s: float
    allowed_tools: tuple[str, ...]
    decision_ref: str | None = None


@dataclass
class Condition:
    """Condition évaluée pour un sujet précis (un nœud, un topic, une zone…)."""

    trigger_id: str
    subject: str
    observed: dict[str, Any]
    threshold: dict[str, Any]
    debounce_s: float
    rule: str


@dataclass
class TriggerEvent:
    """Incident émis par le moteur (vue retournée aux tests et au superviseur)."""

    incident_id: str
    trigger_id: str
    subject: str
    severity: int
    allowed_tools: tuple[str, ...]


_TRIGGERS: tuple[TriggerSpec, ...] = (
    TriggerSpec("TRG-01", "node_absent >= absent_for_s", 3, 3.0, ("context", "param_*", "escalate")),
    TriggerSpec("TRG-02", "endpoint_unavailable >= unavailable_for_s", 3, 2.0, ("context", "param_*", "goal_*", "escalate")),
    TriggerSpec("TRG-03", "age(last_message) > 3 * declared_period", 2, 0.3, ("context", "param_*", "escalate")),
    TriggerSpec("TRG-04", "rate < 50 % nominal pendant 5 s", 2, 5.0, ("context", "param_*", "escalate")),
    TriggerSpec("TRG-05", "qos_incompatible", 2, 0.0, ("context", "param_*", "escalate")),
    TriggerSpec("TRG-06", "tf_absent ou age(tf) > 1 s", 3, 1.0, ("context", "escalate")),
    TriggerSpec("TRG-07", f"thermal_c > {THERMAL_PASSIVE_C} °C", 2, 5.0, ("context", "param_*", "escalate")),
    TriggerSpec("TRG-08", "voltage_v < seuil bas", 3, 3.0, ("context", "param_*", "escalate"), "D-06"),
    TriggerSpec("TRG-09", "disk_free_gb < seuil", 1, 60.0, ("context", "escalate"), "D-07"),
    TriggerSpec("TRG-10", "goal_failed hors politique de reprise", 3, 0.0, ("context", "goal_*", "param_*", "escalate")),
    TriggerSpec("TRG-11", "2 watchdog stops en 30 s sans commande", 4, 0.0, ("context", "safety_stop", "escalate")),
    TriggerSpec("TRG-12", "3 échecs du même outil en 60 s", 2, 0.0, ("context", "param_*", "escalate")),
    TriggerSpec("TRG-13", "exception non gérée hors classes connues", 3, 0.0, ("context", "escalate")),
    TriggerSpec("TRG-14", "unknown_condition signalée par S1", 3, 0.0, ("context", "param_*", "goal_*", "escalate")),
)

TRIGGERS: dict[str, TriggerSpec] = {spec.trigger_id: spec for spec in _TRIGGERS}

#: Seuils issus de décisions non encore validées (D-06, D-07) — repris dans le contexte.
PROVISIONAL_THRESHOLDS: dict[str, tuple[float, str]] = {
    "voltage_low_v": (11.0, "D-06 (proposition, non validée)"),
    "disk_free_min_gb": (5.0, "D-07 (proposition, non validée)"),
}


def _de_bounce_for_period(period_s: float) -> float:
    """TRG-03 : trois périodes déclarées, jamais moins de 100 ms."""
    return max(0.1, 3.0 * period_s)


def _conditions_for(trigger_id: str, obs: Observation) -> list[Condition]:
    """Évalue une règle déclarée et retourne ses conditions vraies."""
    spec = TRIGGERS[trigger_id]
    found: list[Condition] = []

    if trigger_id == "TRG-01":
        for node in obs.nodes:
            if not node.alive:
                found.append(
                    Condition(trigger_id, node.name, {"absent_for_s": node.missing_for_s},
                              {"absent_for_s": spec.debounce_s}, spec.debounce_s, spec.rule)
                )
    elif trigger_id == "TRG-02":
        for endpoint in [*obs.services, *obs.actions]:
            if not endpoint.available:
                found.append(
                    Condition(trigger_id, endpoint.name, {"unavailable_for_s": endpoint.unavailable_for_s},
                              {"unavailable_for_s": spec.debounce_s}, spec.debounce_s, spec.rule)
                )
    elif trigger_id == "TRG-03":
        for topic in obs.topics:
            max_age = 3.0 * topic.declared_period_s
            if topic.age_s > max_age:
                found.append(
                    Condition(trigger_id, topic.name, {"age_s": round(topic.age_s, 3),
                                                      "declared_period_s": topic.declared_period_s},
                              {"max_age_s": round(max_age, 3)},
                              _de_bounce_for_period(topic.declared_period_s), spec.rule)
                )
    elif trigger_id == "TRG-04":
        for topic in obs.topics:
            if topic.nominal_rate_hz > 0 and topic.rate_hz < SLOW_RATE_RATIO * topic.nominal_rate_hz:
                found.append(
                    Condition(trigger_id, topic.name, {"rate_hz": topic.rate_hz},
                              {"min_rate_hz": round(SLOW_RATE_RATIO * topic.nominal_rate_hz, 3)},
                              spec.debounce_s, spec.rule)
                )
    elif trigger_id == "TRG-05":
        for topic in obs.topics:
            if topic.qos_incompatible:
                found.append(
                    Condition(trigger_id, topic.name, {"qos": "incompatible"}, {"qos": "compatible"},
                              spec.debounce_s, spec.rule)
                )
    elif trigger_id == "TRG-06":
        for frame, age in obs.tf_ages.items():
            if age > TF_MAX_AGE_S:
                found.append(
                    Condition(trigger_id, frame, {"age_s": round(age, 3)}, {"max_age_s": TF_MAX_AGE_S},
                              spec.debounce_s, spec.rule)
                )
        for frame in REQUIRED_TF_FRAMES:
            if frame not in obs.tf_ages:
                found.append(
                    Condition(trigger_id, frame, {"present": False}, {"present": True},
                              spec.debounce_s, spec.rule)
                )
    elif trigger_id == "TRG-07":
        for zone, celsius in obs.resources.thermal_c.items():
            if celsius > THERMAL_PASSIVE_C:
                found.append(
                    Condition(trigger_id, zone, {"thermal_c": celsius},
                              {"max_thermal_c": THERMAL_PASSIVE_C}, spec.debounce_s, spec.rule)
                )
    elif trigger_id == "TRG-08":
        threshold = PROVISIONAL_THRESHOLDS["voltage_low_v"][0]
        voltage = obs.resources.voltage_v
        if voltage is not None and voltage < threshold:
            found.append(
                Condition(trigger_id, "battery", {"voltage_v": voltage}, {"min_voltage_v": threshold},
                          spec.debounce_s, spec.rule)
            )
    elif trigger_id == "TRG-09":
        threshold = PROVISIONAL_THRESHOLDS["disk_free_min_gb"][0]
        free = obs.resources.disk_free_gb
        if free < threshold:
            found.append(
                Condition(trigger_id, "root", {"disk_free_gb": free}, {"min_disk_free_gb": threshold},
                          spec.debounce_s, spec.rule)
            )
    elif trigger_id == "TRG-10":
        for failure in obs.failed_goals:
            if not failure.expected:
                found.append(
                    Condition(trigger_id, failure.goal_id, {"action": failure.action, "status": failure.status},
                              {"status": "succeeded"}, spec.debounce_s, spec.rule)
                )
    elif trigger_id == "TRG-11":
        stops = obs.watchdog_stops
        if len(stops) >= 2:
            recent = [at for at in stops if stops[-1] - at <= WATCHDOG_WINDOW_S]
            commanded = obs.last_command_at is not None and obs.last_command_at >= stops[-1]
            if len(recent) >= 2 and not commanded:
                found.append(
                    Condition(trigger_id, "watchdog",
                              {"stops_in_window": len(recent), "last_command_age_s": None},
                              {"max_stops": 1, "window_s": WATCHDOG_WINDOW_S}, spec.debounce_s, spec.rule)
                )
    elif trigger_id == "TRG-12":
        by_tool: dict[str, list[float]] = {}
        for tool, at in obs.tool_failures:
            by_tool.setdefault(tool, []).append(at)
        for tool, stamps in by_tool.items():
            window = [at for at in stamps if stamps[-1] - at <= TOOL_FAILURE_WINDOW_S]
            if len(window) >= TOOL_FAILURE_THRESHOLD:
                found.append(
                    Condition(trigger_id, tool, {"failures": len(window)},
                              {"max_failures": TOOL_FAILURE_THRESHOLD - 1, "window_s": TOOL_FAILURE_WINDOW_S},
                              spec.debounce_s, spec.rule)
                )
    elif trigger_id == "TRG-13":
        for entry in obs.unhandled_exceptions:
            found.append(
                Condition(trigger_id, entry.node, {"message": entry.message}, {"known_class": True},
                          spec.debounce_s, spec.rule)
            )
    elif trigger_id == "TRG-14":
        for condition in obs.unknown_conditions:
            found.append(
                Condition(trigger_id, condition.split(":")[0].strip(), {"reported": condition},
                          {"reported": None}, spec.debounce_s, spec.rule)
            )

    return found


class TriggerEngine:
    """Superviseur de déclenchement : temporisation, cooldown, déduplication, débit."""

    def __init__(self, now: Callable[[], float], state: BridgeState | None = None) -> None:
        self._now = now
        self.state = state if state is not None else BridgeState()
        self._first_seen: dict[tuple[str, str], float] = {}
        self._last_incident_at: dict[tuple[str, str], float] = {}
        self._emissions: dict[str, list[float]] = {}
        self._recovered: set[tuple[str, str]] = set()

    # ------------------------------------------------------------------ règles
    def evaluate_condition(self, trigger_id: str, observation: Observation) -> list[Condition]:
        """Évalue un déclencheur déclaré ; refuse un identifiant hors du jeu clos (TRG-24)."""
        if trigger_id not in TRIGGERS:
            raise ValueError(f"déclencheur non déclaré : {trigger_id} (TRG-24 : jeu clos)")
        return _conditions_for(trigger_id, observation)

    # ---------------------------------------------------------------- cycle
    def observe(self, observation: Observation, now: float) -> list[TriggerEvent]:
        """Évalue les 14 déclencheurs et retourne les incidents nouvellement émis."""
        emitted: list[TriggerEvent] = []
        resolved_pairs = set(observation.recovery_resolved)

        for trigger_id, spec in TRIGGERS.items():
            conditions = self.evaluate_condition(trigger_id, observation)
            active = {(trigger_id, condition.subject): condition for condition in conditions}

            for key in [key for key in self._first_seen if key[0] == trigger_id and key not in active]:
                del self._first_seen[key]

            for key, condition in active.items():
                if self._handle_recovery(key, condition, now, resolved_pairs):
                    continue
                if self._update_open_incident(key, condition, now):
                    continue
                if not self._debounce_elapsed(key, condition, now):
                    continue
                if self._suppressed(key, trigger_id, condition, now):
                    continue
                emitted.append(self._open(key, condition, now))

        return emitted

    # ------------------------------------------------------------- étapes
    def _handle_recovery(
        self, key: tuple[str, str], condition: Condition, now: float, resolved_pairs: set[tuple[str, str]]
    ) -> bool:
        """TRG-22 : une politique de reprise applicable clôt la condition sans S2."""
        if (condition.trigger_id, condition.subject) not in resolved_pairs:
            return False
        if key not in self._recovered:
            self._recovered.add(key)
            self.state.record("recovery_resolved", {"trigger": condition.trigger_id, "subject": condition.subject})
        self._first_seen.pop(key, None)
        return True

    def _debounce_elapsed(self, key: tuple[str, str], condition: Condition, now: float) -> bool:
        first = self._first_seen.setdefault(key, now)
        return now - first >= condition.debounce_s

    def _update_open_incident(self, key: tuple[str, str], condition: Condition, now: float) -> bool:
        """TRG-20 : même déclencheur et même sujet → compteur, pas de doublon."""
        for incident in self.state.incidents.values():
            if (
                incident.state == "open"
                and incident.trigger_id == condition.trigger_id
                and incident.subject == condition.subject
            ):
                incident.occurrences += 1
                incident.payload["trigger"] = _condition_snapshot(condition)
                incident.payload["updated_at"] = now
                self._first_seen.pop(key, None)
                return True
        return False

    def _suppressed(self, key: tuple[str, str], trigger_id: str, condition: Condition, now: float) -> bool:
        """TRG-21 (cooldown) puis D-05 (débit) : journaliser le motif et ne rien ouvrir."""
        last = self._last_incident_at.get(key)
        if last is not None and now - last < COOLDOWN_S:
            self.state.record(
                "trigger_suppressed",
                {"trigger": trigger_id, "subject": condition.subject, "reason": "COOLDOWN",
                 "remaining_s": round(COOLDOWN_S - (now - last), 2)},
            )
            return True

        stamps = [at for at in self._emissions.get(trigger_id, []) if now - at < RATE_WINDOW_S]
        if len(stamps) >= RATE_LIMIT_PER_HOUR:
            self.state.record(
                "trigger_suppressed",
                {"trigger": trigger_id, "subject": condition.subject, "reason": "RATE_LIMIT",
                 "limit_per_hour": RATE_LIMIT_PER_HOUR},
            )
            return True
        return False

    def _open(self, key: tuple[str, str], condition: Condition, now: float) -> TriggerEvent:
        spec = TRIGGERS[condition.trigger_id]
        severity = 4 if condition.trigger_id == "TRG-11" else spec.severity
        allowed = ("context", "safety_stop", "escalate") if severity == 4 else spec.allowed_tools
        incident: Incident = self.state.open_incident(
            spec.trigger_id,
            severity,
            {"trigger": _condition_snapshot(condition)},
            subject=condition.subject,
            allowed_tools=allowed,
        )
        self._last_incident_at[key] = now
        self._emissions.setdefault(spec.trigger_id, []).append(now)
        self._first_seen.pop(key, None)
        return TriggerEvent(
            incident_id=incident.incident_id,
            trigger_id=spec.trigger_id,
            subject=condition.subject,
            severity=severity,
            allowed_tools=allowed,
        )

def _condition_snapshot(condition: Condition) -> dict[str, Any]:
    return {
        "id": condition.trigger_id,
        "severity": TRIGGERS[condition.trigger_id].severity,
        "rule": condition.rule,
        "subject": condition.subject,
        "observed": condition.observed,
        "threshold": condition.threshold,
        "debounce_s": condition.debounce_s,
    }
