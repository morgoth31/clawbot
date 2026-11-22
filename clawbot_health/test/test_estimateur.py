"""Estimateur de cadence et d'âge, sur horloge simulée (REQ-HEALTH-002)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_health.estimateur import EstimateurFlux  # noqa: E402

pytestmark = pytest.mark.req("REQ-HEALTH-002")


def alimenter(est, debut, fin, hz):
    """Enregistre une arrivée toutes les 1/hz secondes, bornes incluses."""
    t = debut
    pas = 1.0 / hz
    while t <= fin + 1e-9:
        est.enregistrer(round(t, 6))
        t += pas


def test_cadence_nominale():
    est = EstimateurFlux(fenetre_s=5.0)
    alimenter(est, 0.0, 5.0, 10.0)
    assert est.cadence(5.0) == pytest.approx(10.0, rel=0.02)


def test_cadence_a_moins_20_pour_cent():
    est = EstimateurFlux(fenetre_s=5.0)
    alimenter(est, 0.0, 5.0, 8.0)
    mesuree = est.cadence(5.0)
    assert mesuree == pytest.approx(8.0, rel=0.02)
    assert mesuree < 9.0, "8 Hz doit être sous le seuil C12 de 10 Hz"


def test_arret_net_perime_au_dela_de_max_age():
    est = EstimateurFlux(fenetre_s=5.0)
    alimenter(est, 0.0, 5.0, 10.0)

    assert est.perime(5.0, max_age_s=1.0) is False
    assert est.age(6.2) == pytest.approx(1.2, abs=1e-6)
    assert est.perime(6.2, max_age_s=1.0) is True
    # fenêtre glissante entièrement vide : la cadence retombe à zéro
    assert est.cadence(20.0) == 0.0


def test_reprise_apres_un_trou():
    est = EstimateurFlux(fenetre_s=5.0)
    alimenter(est, 0.0, 5.0, 10.0)
    # silence de 15 s, puis reprise au même rythme
    alimenter(est, 20.0, 25.0, 10.0)

    assert est.age(25.0) == pytest.approx(0.0, abs=1e-6)
    assert est.perime(25.0, max_age_s=1.0) is False
    assert est.cadence(25.0) == pytest.approx(10.0, rel=0.02)


def test_age_infini_sans_aucun_message():
    est = EstimateurFlux(fenetre_s=5.0)
    assert math.isinf(est.age(1.0))
    assert est.cadence(1.0) == 0.0
    assert est.perime(1.0, max_age_s=1.0) is True
