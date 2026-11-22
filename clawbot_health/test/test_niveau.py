"""Niveau global de RobotHealth et filtrage par capacité (REQ-HEALTH-003/006)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_health.estimateur import (  # noqa: E402
    LEVEL_ERROR, LEVEL_OK, LEVEL_WARN, EtatFlux, Flux, niveau_global, surveilles)

FLUX_LIDAR = Flux(topic="/scan", min_hz=9.0, max_age_s=1.0, capability="lidar", critical=True)
FLUX_CAM = Flux(topic="/camera/depth/image_raw", min_hz=10.0, max_age_s=1.0,
                capability="depth_vision", critical=False)


def etat(flux, *, perime=False, cadence_basse=False, age=0.1, cadence=10.0):
    return EtatFlux(flux=flux, age=age, cadence=cadence, perime=perime,
                    cadence_basse=cadence_basse)


@pytest.mark.req("REQ-HEALTH-003")
def test_tout_sain_donne_ok():
    assert niveau_global([etat(FLUX_LIDAR), etat(FLUX_CAM)]) == LEVEL_OK


@pytest.mark.req("REQ-HEALTH-003")
def test_flux_critique_perime_donne_error():
    assert niveau_global([etat(FLUX_LIDAR, perime=True), etat(FLUX_CAM)]) == LEVEL_ERROR


@pytest.mark.req("REQ-HEALTH-003")
def test_flux_non_critique_perime_donne_warn():
    assert niveau_global([etat(FLUX_LIDAR), etat(FLUX_CAM, perime=True)]) == LEVEL_WARN


@pytest.mark.req("REQ-HEALTH-003")
def test_critique_perime_prime_sur_non_critique_perime():
    etats = [etat(FLUX_CAM, perime=True), etat(FLUX_LIDAR, perime=True)]
    assert niveau_global(etats) == LEVEL_ERROR
    assert niveau_global(list(reversed(etats))) == LEVEL_ERROR


@pytest.mark.req("REQ-HEALTH-002")
def test_flux_lent_seul_donne_warn():
    assert niveau_global([etat(FLUX_LIDAR), etat(FLUX_CAM, cadence=6.0, cadence_basse=True)]) \
        == LEVEL_WARN


@pytest.mark.req("REQ-HEALTH-006")
def test_capacite_inactive_ignoree():
    actives = ["lidar"]
    gardes = surveilles([FLUX_LIDAR, FLUX_CAM], actives)
    assert [f.topic for f in gardes] == ["/scan"]


@pytest.mark.req("REQ-HEALTH-006")
def test_capacite_active_mais_flux_absent_est_perime():
    """Capacité active et aucun message : le flux est périmé, donc signalé."""
    gardes = surveilles([FLUX_CAM], ["depth_vision"])
    assert [f.topic for f in gardes] == ["/camera/depth/image_raw"]

    from clawbot_health.estimateur import EstimateurFlux

    est = EstimateurFlux(fenetre_s=5.0)
    assert est.perime(1.0, max_age_s=gardes[0].max_age_s) is True
