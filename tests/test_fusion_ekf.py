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


@pytest.mark.req("REQ-DRV-011")
def test_la_densite_des_noeuds_slam_est_de_dix_centimetres():
    unite = (RACINE / "services" / "clawbot-slam.service").read_text(encoding="utf-8")
    assert "minimum_travel_distance:=0.1" in unite
    assert "minimum_travel_heading:=0.1" in unite
