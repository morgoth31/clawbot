"""REQ-OPS-055 — les gains de la manette se reglent a chaud, et sont bornes.

Sans rappel de parametre, `ros2 param set linear_scale 0.20` affichait 0.20 pendant que le
noeud continuait d'utiliser 0.06 : le reglage semblait pris et ne changeait rien.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "joy_teleop"))

import clawbot_joy_teleop as teleop  # noqa: E402


@pytest.mark.req("REQ-OPS-055")
@pytest.mark.parametrize("nom, valeur, attendu, accepte", [
    ("linear_scale", 0.20, 0.20, True),
    ("linear_scale", 0.5, 0.5, True),        # butee du pilote, acceptee
    ("linear_scale", 0.0, None, False),      # gain nul = robot sourd, refuse
    ("linear_scale", 0.51, None, False),     # au-dela de MAX_LINEAR_MS
    ("linear_scale", -0.1, None, False),
    ("angular_scale", 0.25, 0.25, True),
    ("angular_scale", 1.5, 1.5, True),       # MAX_ANGULAR_RS, acceptee
    ("angular_scale", 1.6, None, False),
    ("arm_step", 3.0, 3.0, True),
    ("arm_step", 31.0, None, False),
])
def test_les_gains_sont_acceptes_ou_refuses_avec_une_raison(nom, valeur, attendu, accepte):
    ok, resultat = teleop.valider_gain(nom, valeur)
    assert ok is accepte, f"{nom}={valeur} : accepte={ok}, attendu {accepte} ({resultat})"
    if accepte:
        assert isinstance(resultat, float) and resultat == pytest.approx(attendu)


@pytest.mark.req("REQ-OPS-055")
@pytest.mark.parametrize("valeur", [None, "beaucoup", float("nan"), float("inf")])
def test_une_valeur_non_numerique_est_refusee(valeur):
    ok, raison = teleop.valider_gain("linear_scale", valeur)
    assert not ok and raison, f"{valeur!r} devrait etre refuse avec une raison"


@pytest.mark.req("REQ-OPS-055")
def test_un_parametre_non_reglable_traverse_sans_etre_touche():
    ok, resultat = teleop.valider_gain("manette_config", "/tmp/x.yaml")
    assert ok and resultat == "/tmp/x.yaml"


@pytest.mark.req("REQ-OPS-055")
def test_le_noeud_installe_bien_le_rappel_de_parametre():
    """Le code porte l'appel : sans lui, tout le reste est decoratif."""
    source = (RACINE / "joy_teleop" / "clawbot_joy_teleop.py").read_text(encoding="utf-8")
    assert "add_on_set_parameters_callback(self._sur_parametre)" in source
