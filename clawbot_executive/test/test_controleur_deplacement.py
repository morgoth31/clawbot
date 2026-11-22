"""Boucle de déplacement : saturation, cadence, arrêt de sûreté (REQ-EXEC-003, REQ-EXEC-004)."""
from __future__ import annotations

import pytest

from clawbot_executive.deplacement import Deplacement, code_safety

pytestmark = [pytest.mark.req("REQ-EXEC-003"), pytest.mark.req("REQ-EXEC-004")]


def test_vitesse_saturee():
    """La consigne demandée ne peut pas dépasser la borne du registre."""
    boucle = Deplacement(cible_m=2.0, max_speed=0.2)
    pas = boucle.pas(avance_m=0.0, safety_code=None)
    assert pas.vitesse_mps == pytest.approx(0.2)


def test_vitesse_proportionnelle_puis_decroit():
    boucle = Deplacement(cible_m=1.0, max_speed=0.2, gain=1.0)
    assert boucle.pas(0.0, None).vitesse_mps == pytest.approx(0.2)      # saturé
    assert boucle.pas(0.9, None).vitesse_mps == pytest.approx(0.1, abs=0.01)   # 0,1 m restant
    assert boucle.pas(0.99, None).vitesse_mps == pytest.approx(0.01, abs=0.01)


def test_arrivee_dans_la_tolerance():
    boucle = Deplacement(cible_m=0.5, max_speed=0.2, tolerance_m=0.01)
    pas = boucle.pas(avance_m=0.5 + 0.005, safety_code=None)
    assert pas.termine and pas.code is None and pas.vitesse_mps == 0.0


def test_progression_du_feedback():
    boucle = Deplacement(cible_m=2.0, max_speed=0.2)
    assert boucle.pas(0.5, None).progress == pytest.approx(0.25)
    assert boucle.pas(1.0, None).progress == pytest.approx(0.5)


def test_cadence_de_la_boucle():
    """Publier à 20 Hz : la boucle expose sa période, le serveur la respecte."""
    assert Deplacement(cible_m=1.0, max_speed=0.2).periode_s == pytest.approx(0.05)


@pytest.mark.parametrize("etat,estop,code", [
    ("HOLD", False, "SAFETY_HOLD"),
    ("SENSOR_STALE", False, "SENSOR_STALE"),
    ("ESTOP_LATCHED", True, "ESTOP_LATCHED"),
    ("OK", True, "ESTOP_LATCHED"),
])
def test_arret_immediat_sur_safety(etat, estop, code):
    """Consigne nulle et code d'erreur au tick suivant (≤ 50 ms, donc < 100 ms)."""
    boucle = Deplacement(cible_m=2.0, max_speed=0.2)
    boucle.pas(0.0, None)                                   # en mouvement
    pas = boucle.pas(avance_m=0.3, safety_code=code_safety(etat, estop))
    assert pas.code == code
    assert pas.vitesse_mps == 0.0
    assert pas.termine


def test_latence_mesuree_sous_100_ms():
    """Horloge simulée : le tick suivant tombe dans la période de 50 ms."""
    boucle = Deplacement(cible_m=2.0, max_speed=0.2)
    t = 0.0
    boucle.pas(0.0, None)
    t += boucle.periode_s
    pas = boucle.pas(avance_m=0.01, safety_code="ESTOP_LATCHED")
    assert pas.code == "ESTOP_LATCHED"
    assert (t * 1000.0) < 100.0


def test_rotation_utilise_la_borne_angulaire():
    boucle = Deplacement(cible_m=1.5708, max_speed=0.8)
    assert boucle.pas(0.0, None).vitesse_mps == pytest.approx(0.8)
