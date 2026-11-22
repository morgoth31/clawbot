"""Caractérisation de decide() — filet de la refonte P04 (REQ-SAFETY-014).

Ces cas figent le comportement observé du code d'origine : ils doivent passer
AVANT la refonte, puis après, à l'identique. Aucune assertion n'est dérivée de
la nouvelle architecture : ce sont les sorties constatées.

Ordre des garde-fous, tel qu'implémenté : SENSOR_STALE, puis obstacle (STOP),
puis bascule (HOLD / DROP_TORQUE / FREEZE), puis batterie (BATTERY_LOW), sinon OK.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_safety.arbitrator import decide  # noqa: E402

FRAIS = (0.1, 0.0, 0.0)          # consigne de 0,1 m/s
ZERO = (0.0, 0.0, 0.0)
SAIN = [11.9] * 20


def cas(cmd=FRAIS, front=1.0, roll=0.0, pitch=0.0, servo2=96.0,
        samples=SAIN, age_scan=0.1, age_imu=0.1):
    return decide(cmd, front, roll, pitch, servo2, samples, age_scan, age_imu)


# ── sortie nominale ──────────────────────────────────────────────────────────

def test_consigne_passe_quand_tout_va_bien():
    assert cas() == ("OK", FRAIS)


def test_consigne_nulle_reste_nulle():
    assert cas(cmd=ZERO) == ("OK", ZERO)


# ── capteurs périmés ─────────────────────────────────────────────────────────

def test_scan_perime():
    assert cas(age_scan=2.1) == ("SENSOR_STALE", ZERO)


def test_imu_perimee():
    assert cas(age_imu=2.5) == ("SENSOR_STALE", ZERO)


def test_age_non_fini_est_perime():
    assert cas(age_scan=float("nan")) == ("SENSOR_STALE", ZERO)


def test_peremption_avant_obstacle():
    assert cas(front=0.05, age_scan=3.0) == ("SENSOR_STALE", ZERO)


# ── obstacle ─────────────────────────────────────────────────────────────────

def test_obstacle_proche_et_consigne_non_nulle():
    assert cas(front=0.12) == ("STOP", ZERO)


def test_obstacle_proche_sans_vouloir_bouger():
    assert cas(cmd=ZERO, front=0.12) == ("OK", ZERO)


def test_lidar_muet_et_consigne_non_nulle():
    assert cas(front=float("nan")) == ("STOP", ZERO)


def test_lidar_muet_sans_vouloir_bouger():
    assert cas(cmd=ZERO, front=float("nan")) == ("OK", ZERO)


def test_obstacle_avant_bascule():
    assert cas(front=0.10, roll=9.0) == ("STOP", ZERO)


# ── enveloppe du bras et bascule ─────────────────────────────────────────────

def test_bascule_maintien():
    assert cas(roll=9.0) == ("HOLD", ZERO)


def test_bascule_coupe_le_couple_bras_avant():
    assert cas(pitch=13.0, servo2=90.0) == ("DROP_TORQUE", ZERO)


def test_bascule_fige_bras_releve():
    assert cas(pitch=13.0, servo2=100.0) == ("FREEZE", ZERO)


def test_servo_hors_bornes():
    assert cas(servo2=200.0) == ("HOLD", ZERO)


def test_angle_non_fini():
    assert cas(roll=float("nan")) == ("HOLD", ZERO)


# ── tension ──────────────────────────────────────────────────────────────────

def test_batterie_basse_installee():
    assert cas(samples=[10.2] * 30) == ("BATTERY_LOW", ZERO)


def test_pic_de_tension_ne_condamne_pas():
    assert cas(samples=[11.9] * 20 + [10.2] * 2) == ("OK", FRAIS)


def test_aucune_mesure_de_tension():
    assert cas(samples=[]) == ("BATTERY_LOW", ZERO)


def test_batterie_basse_apres_bascule():
    assert cas(roll=9.0, samples=[10.2] * 30) == ("HOLD", ZERO)
