"""REQ-DRV-014 — l'IMU publie des covariances vraies et une cadence reglable.

Le pilote publiait un `Imu()` aux covariances nulles : variance nulle = confiance infinie
pour l'EKF, qui faisait donc une confiance absolue a un gyrometre a 10 Hz. Et
`orientation_covariance[0] = 0` affirmait une orientation valide que le MCU ne fournit pas.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "clawbot_base_driver"))

from clawbot_base_driver import imu_covariances as cov  # noqa: E402


@pytest.mark.req("REQ-DRV-014")
def test_l_orientation_est_declaree_absente():
    matrice = cov.covariance_orientation()
    assert len(matrice) == 9
    assert matrice[0] == -1.0, (
        "orientation_covariance[0] doit valoir -1 : le MCU ne fournit pas d'orientation")
    assert all(v == 0.0 for v in matrice[1:])


@pytest.mark.req("REQ-DRV-014")
def test_les_variance_de_gyro_et_d_acceleration_sont_strictement_positives():
    for nom, matrice in (("gyro", cov.covariance_gyro()), ("accel", cov.covariance_accel())):
        assert len(matrice) == 9
        diagonale = [matrice[i] for i in (0, 4, 8)]
        assert all(v > 0.0 for v in diagonale), f"{nom} : variances nulles {diagonale}"
        assert all(v == 0.0 for i, v in enumerate(matrice) if i not in (0, 4, 8)), (
            f"{nom} : les termes hors diagonale doivent rester nuls")


@pytest.mark.req("REQ-DRV-014")
def test_la_variance_d_acceleration_couvre_le_biais_mesure():
    """Biais mesure au repos le 2026-11-23 : 0,264 et 0,145 m/s2 sur x et y."""
    ecart_type = cov.VARIANCE_ACCEL ** 0.5
    assert ecart_type >= 0.15, (
        f"ecart-type {ecart_type:.3f} m/s2 trop faible devant le biais mesure (0,26)")


@pytest.mark.req("REQ-DRV-014")
def test_une_variance_nulle_est_refusee():
    """Cas negatif : c'est exactement le defaut d'origine."""
    with pytest.raises(ValueError):
        cov.diagonale(1e-4, 0.0, 1e-4)
    with pytest.raises(ValueError):
        cov.diagonale(1e-4, -1.0, 1e-4)


@pytest.mark.req("REQ-DRV-014")
def test_le_pilote_utilise_le_module_et_le_parametre_de_cadence():
    source = (RACINE / "clawbot_base_driver" / "clawbot_base_driver" /
              "base_driver.py").read_text(encoding="utf-8")
    assert "imu.orientation_covariance = covariance_orientation()" in source
    assert "imu.angular_velocity_covariance = covariance_gyro()" in source
    assert "imu.linear_acceleration_covariance = covariance_accel()" in source
    assert "declare_parameter('imu_rate_hz'" in source
    assert "create_timer(0.1, self.pub_data)" not in source, (
        "la cadence ne doit plus etre ecrite en dur a 0,1 s")


@pytest.mark.req("REQ-DRV-014")
def test_la_cadence_par_defaut_correspond_au_mcu():
    """Mesure du 2026-11-23 : 25 Hz demandes donnent 25,0 Hz et 12 % de redondance ;
    50 Hz en donnent 82 %. Le defaut doit rester au point mesure."""
    source = (RACINE / "clawbot_base_driver" / "clawbot_base_driver" /
              "base_driver.py").read_text(encoding="utf-8")
    assert "declare_parameter('imu_rate_hz', 25.0)" in source, (
        "la cadence par defaut doit valoir 25 Hz, cadence mesuree du MCU")
