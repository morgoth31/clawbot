"""REQ-OPS-056 — stick gauche = deplacement, stick droit = rotation (sens trigo a gauche).

L'operateur a demande l'inverse de la disposition d'origine : translation au pouce gauche,
rotation au pouce droit, et un stick de rotation pousse a gauche tourne dans le sens
trigonometrique.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "joy_teleop"))

import clawbot_joy_teleop as teleop  # noqa: E402

LIN = 0.20
ANG = 0.25


@pytest.mark.req("REQ-OPS-056")
@pytest.mark.parametrize("avant, attendu", [(1.0, LIN), (-1.0, -LIN), (0.0, 0.0)])
def test_stick_gauche_vertical_avance_et_recule(avant, attendu):
    x, _, _ = teleop.consigne_vehicule(avant, 0.0, 0.0, LIN, ANG)
    assert x == pytest.approx(attendu)


@pytest.mark.req("REQ-OPS-056")
@pytest.mark.parametrize("droite, attendu", [(-1.0, LIN), (1.0, -LIN), (0.0, 0.0)])
def test_stick_gauche_horizontal_translate_dans_le_bon_sens(droite, attendu):
    """REP-103 : y positif = gauche, donc pousser a droite doit donner un y negatif."""
    _, y, _ = teleop.consigne_vehicule(0.0, droite, 0.0, LIN, ANG)
    assert y == pytest.approx(attendu)


@pytest.mark.req("REQ-OPS-056")
@pytest.mark.parametrize("rotation, attendu", [
    (-1.0, +ANG),   # stick pousse a gauche : sens trigonometrique, z positif
    (+1.0, -ANG),   # stick pousse a droite : sens horaire, z negatif
    (0.0, 0.0),
])
def test_stick_droit_vertical_est_une_rotation_au_bon_sens(rotation, attendu):
    _, _, z = teleop.consigne_vehicule(0.0, 0.0, rotation, LIN, ANG)
    assert z == pytest.approx(attendu)


@pytest.mark.req("REQ-OPS-056")
def test_la_consigne_ne_depasse_jamais_les_butees():
    x, y, z = teleop.consigne_vehicule(5.0, -5.0, 5.0, 10.0, 10.0)
    assert (x, y, z) == (teleop.MAX_LINEAR_MS, teleop.MAX_LINEAR_MS, -teleop.MAX_ANGULAR_RS)


@pytest.mark.req("REQ-OPS-056")
def test_le_mode_vehicule_lit_les_bons_axes():
    """Le code doit lire gauche pour la translation et droit pour la rotation."""
    source = (RACINE / "joy_teleop" / "clawbot_joy_teleop.py").read_text(encoding="utf-8")
    assert 'avant = self._axe(axes, "stick_gauche_y")' in source
    assert 'droite = self._axe(axes, "stick_gauche_x")' in source
    assert 'rotation = self._axe(axes, "stick_droit_x")' in source
    assert 'avant = self._axe(axes, "stick_droit_y")' not in source
