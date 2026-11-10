"""TRG-20 à TRG-24 : invariants de non-déclenchement et de débit."""

from __future__ import annotations

import pytest

from bridge_mcp import triggers
from support import observations
from support.fake_clock import FakeClock

pytestmark = pytest.mark.contract


def _fire(engine: triggers.TriggerEngine, clock: FakeClock, trigger_id: str, *, ticks: int = 40):
    """Provoque la condition jusqu'à obtenir un incident, retourne la première émission."""
    debounce = triggers.TRIGGERS[trigger_id].debounce_s
    for _ in range(max(ticks, int(debounce / 0.1) + 3)):
        observation = observations.FAULTS[trigger_id](observations.nominal(clock.now()), clock.now())
        emitted = engine.observe(observation, clock.now())
        if emitted:
            return emitted[0]
        clock.advance(0.1)
    raise AssertionError(f"{trigger_id}: aucun incident émis")


def test_dedup_updates_open_incident_instead_of_creating_a_new_one():
    """TRG-20 : même déclencheur + même sujet → compteur incrémenté, pas de doublon."""
    clock = FakeClock()
    engine = triggers.TriggerEngine(clock.now)
    first = _fire(engine, clock, "TRG-01")

    clock.advance(1.0)
    again = []
    for _ in range(5):
        observation = observations.FAULTS["TRG-01"](observations.nominal(clock.now()), clock.now())
        again.extend(engine.observe(observation, clock.now()))
        clock.advance(0.1)

    assert again == [], "un incident ouvert ne doit pas être dupliqué"
    open_incidents = [inc for inc in engine.state.incidents.values() if inc.state == "open"]
    assert len(open_incidents) == 1
    assert open_incidents[0].incident_id == first.incident_id
    assert open_incidents[0].occurrences >= 2


def test_cooldown_blocks_new_incident_and_journals_it():
    """TRG-21 : après clôture, un nouvel événement dans le cooldown est journalisé, pas ouvert."""
    clock = FakeClock()
    engine = triggers.TriggerEngine(clock.now)
    first = _fire(engine, clock, "TRG-05")

    incident = engine.state.get(first.incident_id)
    assert incident is not None
    incident.state = "closed"
    engine.state.record("incident_close", {"incident_id": incident.incident_id})

    clock.advance(10.0)  # cooldown de 60 s non écoulé
    emitted = []
    for _ in range(5):
        observation = observations.FAULTS["TRG-05"](observations.nominal(clock.now()), clock.now())
        emitted.extend(engine.observe(observation, clock.now()))
        clock.advance(0.1)

    assert emitted == []
    assert any(entry.get("reason") == "COOLDOWN" for entry in engine.state.audit)
    assert sum(1 for inc in engine.state.incidents.values() if inc.trigger_id == "TRG-05") == 1

    clock.advance(61.0)
    second = None
    for _ in range(5):
        observation = observations.FAULTS["TRG-05"](observations.nominal(clock.now()), clock.now())
        emitted = engine.observe(observation, clock.now())
        if emitted:
            second = emitted[0]
            break
        clock.advance(0.1)

    assert second is not None and second.incident_id != first.incident_id


def test_recovery_policy_resolves_without_calling_system_two():
    """TRG-22 : une politique de reprise applicable clôt la condition sans incident."""
    clock = FakeClock()
    engine = triggers.TriggerEngine(clock.now)

    observation = observations.FAULTS["TRG-01"](observations.nominal(clock.now()), clock.now())
    observation.recovery_resolved = [("TRG-01", "/driver_node")]

    emitted = []
    for _ in range(40):
        emitted.extend(engine.observe(observation, clock.now()))
        clock.advance(0.1)

    assert emitted == []
    assert any(entry.get("event") == "recovery_resolved" for entry in engine.state.audit)


def test_rate_limit_caps_incidents_per_hour():
    """D-05 : au plus 6 incidents par heure et par déclencheur."""
    clock = FakeClock()
    engine = triggers.TriggerEngine(clock.now)
    emitted_total = 0

    for _ in range(9):
        emitted = []
        for _ in range(40):
            observation = observations.FAULTS["TRG-05"](observations.nominal(clock.now()), clock.now())
            emitted.extend(engine.observe(observation, clock.now()))
            if emitted:
                break
            clock.advance(0.1)
        for incident in list(engine.state.incidents.values()):
            incident.state = "closed"
        emitted_total += len(emitted)
        clock.advance(61.0)  # sortir du cooldown

    assert emitted_total <= 6
    assert any(entry.get("reason") == "RATE_LIMIT" for entry in engine.state.audit)


def test_undeclared_trigger_is_refused():
    """TRG-24 : aucun déclencheur hors du jeu clos ne peut être enregistré."""
    clock = FakeClock()
    engine = triggers.TriggerEngine(clock.now)
    with pytest.raises(ValueError):
        engine.evaluate_condition("TRG-99", observations.nominal(clock.now()))
