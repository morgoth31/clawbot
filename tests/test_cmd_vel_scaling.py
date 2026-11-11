"""ERR-009 : la consigne doit rester proportionnelle et ne pas fuir sous le seuil mort."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yahboomcar_bringup" / "yahboomcar_bringup"))

from cmd_scaling import MAX_LINEAR, scale_cmd_vel, scale_linear  # noqa: E402


def test_command_is_proportional():
    assert scale_linear(0.2) == 0.2
    assert abs(scale_linear(0.1) - 0.1) < 1e-9
    assert abs(scale_linear(0.05) - 0.05) < 1e-9


def test_deadband_does_not_leak_motion():
    assert scale_cmd_vel(0.001, 0.0, 0.0)[0] == 0.0
    assert scale_cmd_vel(0.0, -0.001, 0.0)[1] == 0.0
    assert scale_cmd_vel(0.0, 0.0, 0.005)[2] == 0.0


def test_command_is_clamped_to_limits():
    assert scale_linear(10.0) == MAX_LINEAR
    assert scale_linear(-10.0) == -MAX_LINEAR


def test_nan_never_reaches_the_mcu():
    assert scale_cmd_vel(float("nan"), float("inf"), float("-inf")) == (0.0, 0.0, 0.0)


def test_lateral_axis_is_handled_like_forward():
    # base mecanum : vy est une vraie consigne, pas un bruit
    assert scale_cmd_vel(0.0, 0.1, 0.0)[1] == 0.1
