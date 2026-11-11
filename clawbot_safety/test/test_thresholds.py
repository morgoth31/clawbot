"""Les seuils du Système 1 : chaque cas correspond à un incident réel ou plausible."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_safety.thresholds import (  # noqa: E402
    battery_state, is_stale, obstacle_stop, tilt_state,
)


def test_tilt_hold_at_eight_degrees():
    assert tilt_state(0.0, 7.9, 90) == "ok"
    assert tilt_state(0.0, 8.1, 90) == "hold"


def test_torque_cut_only_when_arm_is_forward():
    assert tilt_state(0.0, 12.5, 70) == "drop_torque"   # extension avant : chute vers le sol
    assert tilt_state(0.0, 12.5, 96) == "freeze"        # relevé arrière : chute contre le mât


def test_invalid_angle_is_treated_as_stop():
    assert tilt_state(float("nan"), 0.0, 90) == "hold"
    assert tilt_state(0.0, 0.0, -5.0) == "hold"          # cas réel : angle de servo invalide


def test_obstacle_stop_needs_motion():
    assert obstacle_stop(0.12, True) is True
    assert obstacle_stop(0.12, False) is False


def test_blind_lidar_blocks_motion():
    assert obstacle_stop(float("nan"), True) is True


def test_battery_ignores_motor_current_spike():
    samples = [11.9] * 20 + [10.4]          # pic transitoire en fin de fenêtre
    assert battery_state(samples, now_s=10.0) == "ok"


def test_battery_low_when_sag_persists():
    samples = [10.3] * 30                   # trois secondes sous le seuil
    assert battery_state(samples, now_s=10.0) == "low"


def test_stale_flow_is_an_alert():
    assert is_stale(0.1) is False
    assert is_stale(2.5) is True
    assert is_stale(float("nan")) is True
