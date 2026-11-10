"""TRG-A1 et TRG-A2 : chaque déclencheur émet, et n'émet pas sous le seuil.

Le jeu est clos (TRG-24) : le test échoue si le catalogue et les cas couverts divergent.
"""

from __future__ import annotations

import pytest

from bridge_mcp import triggers
from support import observations
from support.fake_clock import FakeClock

pytestmark = pytest.mark.contract


def _engine() -> tuple[triggers.TriggerEngine, FakeClock]:
    clock = FakeClock()
    return triggers.TriggerEngine(clock.now), clock


def test_catalogue_covers_fourteen_triggers():
    """TRG-24 : le jeu TRG-01..TRG-14 est clos et entièrement décrit."""
    assert set(triggers.TRIGGERS) == {f"TRG-{n:02d}" for n in range(1, 15)}
    assert set(observations.FAULTS) == set(triggers.TRIGGERS)


@pytest.mark.parametrize("trigger_id", sorted(observations.FAULTS))
def test_trigger_fires_with_expected_severity_and_tools(trigger_id: str):
    """TRG-A1 : condition vraie → un incident, bon identifiant, bonne sévérité, bons droits."""
    engine, clock = _engine()
    spec = triggers.TRIGGERS[trigger_id]

    observation = observations.FAULTS[trigger_id](observations.nominal(clock.now()), clock.now())
    incidents = engine.observe(observation, clock.now())

    # franchir le debounce, un pas à la fois
    for _ in range(int(spec.debounce_s / 0.1) + 2):
        if incidents:
            break
        clock.advance(0.1)
        incidents = engine.observe(observation, clock.now())

    assert [i.trigger_id for i in incidents] == [trigger_id]
    incident = incidents[0]
    assert incident.severity == spec.severity
    assert set(incident.allowed_tools) == set(spec.allowed_tools)
    assert incident.trigger_id in {f"TRG-{n:02d}" for n in range(1, 15)}


@pytest.mark.parametrize("trigger_id", sorted(observations.FAULTS))
def test_no_trigger_below_threshold(trigger_id: str):
    """TRG-A2 : condition sous le seuil → aucun incident, même après le debounce."""
    engine, clock = _engine()
    spec = triggers.TRIGGERS[trigger_id]
    observation = observations.nominal(clock.now())

    for _ in range(int(spec.debounce_s / 0.1) + 5):
        assert engine.observe(observation, clock.now()) == []
        clock.advance(0.1)


def test_severity_four_restricts_mutations():
    """TRG-23 / SAF-05 : un incident de sévérité 4 n'ouvre que `safety_stop` et `escalate`."""
    engine, clock = _engine()
    spec = triggers.TRIGGERS["TRG-11"]
    assert spec.severity == 4

    incident = None
    for _ in range(5):
        observation = observations.FAULTS["TRG-11"](observations.nominal(clock.now()), clock.now())
        incidents = engine.observe(observation, clock.now())
        if incidents:
            incident = incidents[0]
            break
        clock.advance(0.1)

    assert incident is not None
    mutations = {tool for tool in incident.allowed_tools if not tool.startswith("context")}
    assert mutations == {"safety_stop", "escalate"}
