"""REQ-DRV-011 — chaque grandeur de l'EKF n'a qu'une source ; le SLAM a une densite connue.

`vyaw` etait fusionne deux fois (roues et IMU) : deux mesures contradictoires de la meme
grandeur, dont la moins fiable venait des roues d'une base mecanum. Et les parametres du
SLAM vivaient en ligne de commande dans l'unite, tandis que
`config/slam_toolbox_mapping.yaml` dormait sans etre charge, avec des valeurs differentes.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[1]
GRANDEURS = ['x', 'y', 'z', 'roll', 'pitch', 'yaw', 'vx', 'vy', 'vz',
             'vroll', 'vpitch', 'vyaw', 'ax', 'ay', 'az']


def _ekf() -> dict:
    doc = yaml.safe_load((RACINE / "config" / "ekf.yaml").read_text(encoding="utf-8"))
    return doc["ekf_filter_node"]["ros__parameters"]


def _actifs(cle: str, params: dict) -> set[str]:
    return {GRANDEURS[i] for i, v in enumerate(params.get(cle) or []) if v}


@pytest.mark.req("REQ-DRV-011")
def test_aucune_grandeur_n_est_fusionnee_depuis_deux_sources():
    params = _ekf()
    doubles = _actifs("odom0_config", params) & _actifs("imu0_config", params)
    assert not doubles, (
        f"grandeurs fusionnees depuis /odom_raw ET /imu/data_raw : {sorted(doubles)} — "
        "deux mesures contradictoires, la moins fiable venant des roues (REQ-DRV-011)")


@pytest.mark.req("REQ-DRV-011")
def test_le_lacet_vient_de_l_imu():
    params = _ekf()
    assert "vyaw" in _actifs("imu0_config", params), "l'IMU doit fournir le taux de lacet"
    assert "vyaw" not in _actifs("odom0_config", params), "les roues ne doivent pas le fournir"


@pytest.mark.req("REQ-DRV-011")
def test_les_roues_fournissent_la_translation():
    actifs = _actifs("odom0_config", _ekf())
    assert {"vx", "vy"} <= actifs, f"/odom_raw doit fournir vx et vy, actifs={sorted(actifs)}"


@pytest.mark.req("REQ-DRV-011")
def test_un_double_serait_detecte():
    """Cas negatif : sans lui, le marqueur serait de complaisance."""
    faux = {"odom0_config": [False] * 6 + [True, True, False, False, False, True] + [False] * 3,
            "imu0_config": [False] * 11 + [True] + [False] * 3}
    doubles = _actifs("odom0_config", faux) & _actifs("imu0_config", faux)
    assert doubles == {"vyaw"}, f"le detecteur doit voir vyaw, il a vu {doubles}"


@pytest.mark.req("REQ-DRV-011")
def test_l_unite_slam_et_le_yaml_ne_divergent_pas():
    """Les deux portent les memes valeurs : sinon l'une des deux est de la config morte."""
    import re

    unite = (RACINE / "services" / "clawbot-slam.service").read_text(encoding="utf-8")
    doc = yaml.safe_load((RACINE / "config" / "slam_toolbox_mapping.yaml").read_text(encoding="utf-8"))
    params = doc["slam_toolbox"]["ros__parameters"]
    lus = dict(re.findall(r"-p ([a-z_]+):=([A-Za-z0-9_.]+)", unite))
    for cle, valeur_cli in lus.items():
        assert cle in params, f"{cle} passe par l'unite mais absent du YAML"
        # `false` en YAML et `False` en Python designent la meme valeur.
        valeur_yaml = str(params[cle]).lower()
        assert valeur_yaml == valeur_cli.lower(), (
            f"{cle} : unite={valeur_cli} / yaml={valeur_yaml} — une des deux est morte")


@pytest.mark.req("REQ-DRV-012")
def test_le_slam_ne_jette_pas_quatre_scans_sur_cinq():
    """Le lidar publie a 10 Hz : un intervalle de 0,5 s n'integere qu'un scan sur cinq."""
    unite = (RACINE / "services" / "clawbot-slam.service").read_text(encoding="utf-8")
    assert "minimum_time_interval:=0.1" in unite, (
        "minimum_time_interval doit valoir 0,1 s pour exploiter les 10 Hz du lidar")


@pytest.mark.req("REQ-DRV-012")
def test_le_graphe_est_densifie_en_translation_et_en_rotation():
    unite = (RACINE / "services" / "clawbot-slam.service").read_text(encoding="utf-8")
    assert "minimum_travel_distance:=0.05" in unite
    assert "minimum_travel_heading:=0.05" in unite


@pytest.mark.req("REQ-DRV-012")
def test_la_recherche_du_scan_matching_est_elargie():
    unite = (RACINE / "services" / "clawbot-slam.service").read_text(encoding="utf-8")
    assert "correlation_search_space_dimension:=0.8" in unite, (
        "0,5 m est trop court pour rattraper une erreur de lacet en virage")


@pytest.mark.req("REQ-DRV-013")
def test_le_slam_ignore_les_echos_de_sa_propre_structure():
    """15 points mesures entre 0,039 et 0,184 m, de -139 a +108 deg : le robot se voit."""
    unite = (RACINE / "services" / "clawbot-slam.service").read_text(encoding="utf-8")
    assert "min_laser_range:=0.15" in unite, (
        "sans portee minimale, le lidar cartographie sa propre structure")


@pytest.mark.req("REQ-DRV-013")
def test_la_portee_maximale_est_bornee_au_reel():
    unite = (RACINE / "services" / "clawbot-slam.service").read_text(encoding="utf-8")
    assert "max_laser_range:=8.0" in unite, "portee mesuree 5,6 m : 25 m n'apporte que du bruit"


@pytest.mark.req("REQ-DRV-013")
def test_l_ekf_rejette_une_mesure_de_vitesse_aberrante():
    params = _ekf()
    seuil = params.get("odom0_twist_rejection_threshold")
    assert seuil is not None, (
        "aucun seuil Mahalanobis : un glissement de roue mecanum est fusionne tel quel")
    assert 1.0 <= float(seuil) <= 5.0, f"seuil {seuil} hors de la plage utile 1-5"


@pytest.mark.req("REQ-DRV-013")
def test_un_seuil_absent_serait_detecte():
    """Cas negatif : un YAML sans seuil doit echouer, pas passer par defaut."""
    params = {"odom0_config": [False] * 15, "imu0_config": [False] * 15}
    assert params.get("odom0_twist_rejection_threshold") is None
