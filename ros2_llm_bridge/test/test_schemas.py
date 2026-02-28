import math

import pytest
from pydantic import ValidationError

from ros2_llm_bridge.schemas import (
    Beep,
    ControlArm,
    ControlClaw,
    SetArmPose,
    SetLamps,
    SetVelocity,
    Speak,
    Stop,
)


# --- SetVelocity ---

def test_set_velocity_valid():
    cmd = SetVelocity(linear_x=1.0, linear_y=0.0, angular_z=0.5)
    assert cmd.linear_x == 1.0
    assert cmd.linear_y == 0.0
    assert cmd.angular_z == 0.5


def test_set_velocity_default_linear_y():
    cmd = SetVelocity(linear_x=1.0, angular_z=0.0)
    assert cmd.linear_y == 0.0


def test_set_velocity_invalid_angular_z_too_high():
    with pytest.raises(ValidationError):
        SetVelocity(linear_x=0.0, angular_z=math.pi + 0.1)


def test_set_velocity_invalid_angular_z_too_low():
    with pytest.raises(ValidationError):
        SetVelocity(linear_x=0.0, angular_z=-(math.pi + 0.1))


# --- Stop ---

def test_stop_valid():
    assert Stop() is not None


# --- Speak ---

def test_speak_valid():
    cmd = Speak(text="Hello world")
    assert cmd.text == "Hello world"


# --- ControlClaw ---

def test_control_claw_open():
    cmd = ControlClaw(state="open")
    assert cmd.state == "open"


def test_control_claw_close():
    cmd = ControlClaw(state="close")
    assert cmd.state == "close"


def test_control_claw_invalid_state():
    with pytest.raises(ValidationError):
        ControlClaw(state="wiggle")


# --- SetLamps ---

def test_set_lamps_valid():
    cmd = SetLamps(r=255, g=128, b=0)
    assert cmd.r == 255


def test_set_lamps_r_above_255():
    with pytest.raises(ValidationError):
        SetLamps(r=256, g=0, b=0)


def test_set_lamps_g_below_0():
    with pytest.raises(ValidationError):
        SetLamps(r=0, g=-1, b=0)


# --- SetArmPose ---

def test_set_arm_pose_valid():
    cmd = SetArmPose(pose_id=1)
    assert cmd.pose_id == 1


def test_set_arm_pose_too_low():
    with pytest.raises(ValidationError):
        SetArmPose(pose_id=0)


def test_set_arm_pose_too_high():
    with pytest.raises(ValidationError):
        SetArmPose(pose_id=4)


# --- ControlArm ---

def test_control_arm_valid():
    cmd = ControlArm(joints_array=[0.0, 1.57, -0.5, 0.0])
    assert len(cmd.joints_array) == 4


# --- Beep ---

def test_beep_default():
    cmd = Beep()
    assert cmd.delay_ms == 100


def test_beep_zero_invalid():
    with pytest.raises(ValidationError):
        Beep(delay_ms=0)


def test_beep_negative_invalid():
    with pytest.raises(ValidationError):
        Beep(delay_ms=-50)
