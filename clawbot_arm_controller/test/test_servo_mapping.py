"""Tests de la conversion articulation -> servo et de son interpretation inverse."""

import math

import pytest

from clawbot_arm_controller.servo_mapping import (
    ServoSpec,
    default_arm_specs,
    default_gripper_spec,
    specs_from_parameters,
)


def test_bornes_basse_et_haute_des_cinq_axes():
    """q = -90° -> 0°, q = 0 -> 90°, q = +90° -> 180° pour les axes 1 a 4."""
    specs = default_arm_specs()
    assert [s.joint for s in specs] == [f'arm_joint{i}' for i in range(1, 6)]
    for spec in specs[:4]:
        assert spec.to_servo_deg(-math.pi / 2) == pytest.approx(0.0)
        assert spec.to_servo_deg(0.0) == pytest.approx(90.0)
        assert spec.to_servo_deg(math.pi / 2) == pytest.approx(180.0)


def test_cinquieme_axe_va_jusqu_a_270():
    spec = default_arm_specs()[4]
    assert spec.max_deg == 270.0
    assert spec.to_servo_deg(math.pi) == pytest.approx(270.0)
    assert spec.to_servo_deg(-math.pi / 2) == pytest.approx(0.0)


def test_pince_fermee_a_180_et_ouverte_a_0():
    spec = default_gripper_spec()
    assert spec.joint == 'grip_joint'
    assert spec.servo_id == 6
    assert spec.to_servo_deg(0.0) == pytest.approx(180.0)
    assert spec.to_servo_deg(-1.54) == pytest.approx(0.0)


def test_les_bornes_servo_ecrasent_la_consigne():
    spec = default_arm_specs()[0]
    assert spec.to_servo_deg(10.0) == 180.0
    assert spec.to_servo_deg(-10.0) == 0.0


def test_aller_retour_sans_saturation():
    for spec in default_arm_specs() + [default_gripper_spec()]:
        for q in (0.0, 0.4, -0.4):
            servo = spec.to_servo_deg(q)
            if servo in (spec.min_deg, spec.max_deg):
                continue
            assert spec.to_joint_rad(servo) == pytest.approx(q, abs=1e-9)


def test_parametres_incoherents_refuses():
    with pytest.raises(ValueError):
        specs_from_parameters(['a'], [1, 2], [0.0], [1.0], [0.0], [1.0])
    with pytest.raises(ValueError):
        specs_from_parameters(['a'], [1], [0.0], [0.0], [0.0], [180.0])
    with pytest.raises(ValueError):
        specs_from_parameters(['a'], [1], [0.0], [1.0], [180.0], [0.0])


def test_servo_spec_est_immuable():
    spec = ServoSpec('j', 1, 90.0, 57.29577951, 0.0, 180.0)
    with pytest.raises(Exception):
        spec.zero_deg = 0.0
