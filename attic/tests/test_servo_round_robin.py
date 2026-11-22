"""Le budget UART du driver : une lecture par tick, jamais deux."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yahboomcar_bringup" / "yahboomcar_bringup"))

from round_robin import RoundRobin  # noqa: E402


def test_one_servo_per_tick_when_active():
    rr = RoundRobin()
    assert [rr.next_servo() for _ in range(6)] == [1, 2, 3, 4, 5, 6]
    assert rr.next_servo() == 1          # cycle complet en 600 ms à 10 Hz


def test_servo_read_is_skipped_at_rest():
    rr = RoundRobin(idle_period_ticks=10)
    assert rr.next_servo(arm_at_rest=True) == 1
    assert rr.next_servo(arm_at_rest=True) is None
    assert rr.next_servo(arm_at_rest=True) is None


def test_cycle_covers_all_six():
    rr = RoundRobin()
    assert rr.cycle_ticks() == 6
