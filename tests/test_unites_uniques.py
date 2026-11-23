"""REQ-DRV-010 — une unite ne doit exister qu'une fois, et le lidar doit charger son YAML.

`clawbot-lidar.service` a existe en double : `services/` (sans `params_file`, utilise par
/etc) et `systemd/` (avec). Le pilote demarrait donc sans sa configuration, prenait
`frame_id: laser` au lieu de `laser_link`, et slam_toolbox jetait chaque scan — aucune
carte produite pendant tout le parcours du 2026-11-23.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[1]
DOSSIERS = (RACINE / "services", RACINE / "systemd")


@pytest.mark.req("REQ-DRV-010")
def test_aucune_unite_n_existe_en_double():
    doublons = []
    for a, b in ((DOSSIERS[0], DOSSIERS[1]),):
        noms_a = {p.name for p in a.glob("*.service")}
        noms_b = {p.name for p in b.glob("*.service")}
        doublons = sorted(noms_a & noms_b)
    assert not doublons, (
        f"unites presentes dans services/ ET systemd/ : {doublons} — laquelle /etc pointe-t-il ? "
        "Supprimer la variante obsolete (REQ-DRV-010)")


@pytest.mark.req("REQ-DRV-010")
def test_l_unite_du_lidar_charge_sa_configuration():
    unites = [p for d in DOSSIERS for p in d.glob("clawbot-lidar.service")]
    assert len(unites) == 1, f"attendu une seule unite lidar, trouve {[u for u in unites]}"
    texte = unites[0].read_text(encoding="utf-8")
    assert "params_file" in texte, "l'unite du lidar ne passe pas params_file"
    assert "ydlidar_x3plus.yaml" in texte


@pytest.mark.req("REQ-DRV-010")
def test_le_repere_du_lidar_correspond_a_l_arbre_tf():
    """Le frame_id declare doit etre celui que l'URDF publie : sinon SLAM jette tout."""
    config = yaml.safe_load((RACINE / "config" / "ydlidar_x3plus.yaml").read_text(encoding="utf-8"))
    declare = config["ydlidar_ros2_driver_node"]["ros__parameters"]["frame_id"]
    assert declare == "laser_link", (
        f"frame_id declare '{declare}' : l'arbre TF publie 'laser_link', "
        "slam_toolbox jetterait chaque scan")


@pytest.mark.req("REQ-DRV-010")
def test_un_doublon_serait_detecte(tmp_path):
    """Cas negatif : sans lui, le marqueur serait de complaisance."""
    a, b = tmp_path / "services", tmp_path / "systemd"
    for d in (a, b):
        d.mkdir()
        (d / "clawbot-lidar.service").write_text("[Unit]\n", encoding="utf-8")
    noms = {p.name for p in a.glob("*.service")} & {p.name for p in b.glob("*.service")}
    assert noms == {"clawbot-lidar.service"}, f"le detecteur doit voir le doublon, il a vu {noms}"
