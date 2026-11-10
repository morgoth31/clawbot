"""TRG-A4 : latence condition vraie → émission < debounce + 200 ms, sur 100 occurrences."""

from __future__ import annotations

import pytest

from bridge_mcp import triggers
from support import observations
from support.fake_clock import FakeClock

pytestmark = pytest.mark.contract

TICK_S = 0.1


def _measure(trigger_id: str, *, repetitions: int = 100) -> list[float]:
    """Retourne la latence mesurée pour chaque répétition, en secondes."""
    spec = triggers.TRIGGERS[trigger_id]
    latencies: list[float] = []

    for n in range(repetitions):
        clock = FakeClock(start=1000.0 + n * 100.0)
        engine = triggers.TriggerEngine(clock.now)
        condition_at = clock.now()
        emitted_at: float | None = None

        for _ in range(int((spec.debounce_s + 1.0) / TICK_S) + 5):
            observation = observations.FAULTS[trigger_id](observations.nominal(clock.now()), clock.now())
            if engine.observe(observation, clock.now()):
                emitted_at = clock.now()
                break
            clock.advance(TICK_S)

        assert emitted_at is not None, f"{trigger_id}: aucune émission en {repetitions} répétitions"
        latencies.append(emitted_at - condition_at)

    return latencies


@pytest.mark.parametrize("trigger_id", ["TRG-01", "TRG-07", "TRG-09", "TRG-05"])
def test_latency_stays_within_debounce_plus_200ms(trigger_id: str):
    """TRG-A4 : la temporisation ne dérive pas au-delà de debounce + 200 ms."""
    spec = triggers.TRIGGERS[trigger_id]
    latencies = _measure(trigger_id)

    assert len(latencies) == 100
    worst = max(latencies)
    assert worst <= spec.debounce_s + 0.2, (
        f"{trigger_id}: latence max {worst:.2f} s > {spec.debounce_s + 0.2:.2f} s autorisé"
    )
    assert worst >= spec.debounce_s * 0.9, (
        f"{trigger_id}: émission prématurée ({worst:.2f} s) avant le debounce ({spec.debounce_s} s)"
    )
