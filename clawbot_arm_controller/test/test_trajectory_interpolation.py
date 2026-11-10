"""Tests de l'echantillonnage temporel des trajectoires."""

import math

import pytest

from clawbot_arm_controller.servo_mapping import interpolate


def test_nombre_d_echantillons_et_bornes():
    """1 s a 10 Hz : 11 echantillons, premier a t=0, dernier a t=1."""
    samples = interpolate([(0.0, [0.0]), (1.0, [1.0])], 0.1)
    assert len(samples) == 11
    assert samples[0] == (0.0, [0.0])
    assert samples[-1][0] == pytest.approx(1.0)
    assert samples[-1][1] == pytest.approx([1.0])


def test_interpolation_lineaire_au_milieu():
    samples = interpolate([(0.0, [0.0, 2.0]), (2.0, [1.0, 0.0])], 0.5)
    milieu = [q for t, q in samples if abs(t - 1.0) < 1e-9][0]
    assert milieu[0] == pytest.approx(0.5)
    assert milieu[1] == pytest.approx(1.0)


def test_le_dernier_point_est_toujours_present_si_la_periode_ne_divise_pas():
    samples = interpolate([(0.0, [0.0]), (0.25, [1.0])], 0.1)
    assert samples[-1][0] == pytest.approx(0.25)
    assert samples[-1][1] == pytest.approx([1.0])


def test_temps_croissants():
    samples = interpolate([(0.0, [0.0]), (0.5, [1.0]), (0.7, [2.0])], 0.05)
    times = [t for t, _ in samples]
    assert times == sorted(times)
    assert len(set(times)) == len(times)


def test_point_unique_est_tenu():
    assert interpolate([(0.3, [0.2, -0.1])], 0.1) == [(0.3, [0.2, -0.1])]


def test_point_apres_le_debut_est_tenu_avant_son_instant():
    samples = interpolate([(0.5, [0.7])], 0.1)
    assert samples == [(0.5, [0.7])]


def test_dates_decroissantes_refusees():
    with pytest.raises(ValueError):
        interpolate([(1.0, [0.0]), (0.5, [1.0])], 0.1)


def test_dimensions_incoherentes_refusees():
    with pytest.raises(ValueError):
        interpolate([(0.0, [0.0]), (1.0, [0.0, 1.0])], 0.1)


def test_periode_non_positive_refusee():
    with pytest.raises(ValueError):
        interpolate([(0.0, [0.0]), (1.0, [1.0])], 0.0)


def test_trajectoire_vide():
    assert interpolate([], 0.1) == []


def test_les_positions_restent_dans_la_fourchette_des_points():
    samples = interpolate([(0.0, [0.0]), (1.0, [2.0]), (2.0, [1.0])], 0.1)
    values = [q for _, positions in samples for q in positions]
    assert min(values) == pytest.approx(0.0)
    assert max(values) == pytest.approx(2.0)
