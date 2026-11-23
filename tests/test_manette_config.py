"""REQ-OPS-054 — une config de manette livrée ne contient aucun axe mort.

`config/manette.yaml` a déclaré `stick_droit_x` avec `min = max = 0.0` du 2026-11-15 au
2026-11-23 : `manette_config._lire_axe` refuse alors le fichier entier, et aucun nœud de
téléopération ne démarre. Le défaut a survécu huit jours parce qu'aucun test ne lisait ce
fichier.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[1]
CONFIG = RACINE / "config" / "manette.yaml"
DEBATTEMENT_MINIMAL = 0.5


@pytest.mark.req("REQ-OPS-054")
def test_aucun_axe_de_la_manette_n_est_mort():
    document = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    axes = document.get("axes") or {}
    assert axes, "la configuration ne déclare aucun axe"
    morts = []
    for nom, axe in axes.items():
        debattement = abs(float(axe["max"]) - float(axe["min"]))
        if debattement < DEBATTEMENT_MINIMAL:
            morts.append(f"{nom}={debattement:.2f} (min {axe['min']}, max {axe['max']})")
    assert not morts, (
        f"{CONFIG.name} : axes au débattement insuffisant : {morts} — le téléop refuse "
        "alors le fichier entier (manette_config.py, REQ-OPS-054)")


@pytest.mark.req("REQ-OPS-054")
def test_le_controle_sait_refuser_un_axe_mort(tmp_path):
    """Cas negatif : sans lui, le marqueur serait de complaisance."""
    faux = tmp_path / "manette.yaml"
    faux.write_text(yaml.safe_dump({"axes": {"stick_droit_x": {
        "index": 2, "centre": 0.0, "min": 0.0, "max": 0.0, "zone_morte": 0.08}}}),
        encoding="utf-8")
    axes = yaml.safe_load(faux.read_text(encoding="utf-8"))["axes"]
    morts = [nom for nom, a in axes.items()
             if abs(float(a["max"]) - float(a["min"])) < DEBATTEMENT_MINIMAL]
    assert morts == ["stick_droit_x"], f"le controle doit voir l'axe mort, il a vu {morts}"


@pytest.mark.req("REQ-OPS-053")
def test_la_config_declaredes_boutons_et_les_axes_attendus():
    document = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert document["appareil"]["js_pad"] == "/dev/input/js0"
    assert document.get("boutons"), "les boutons ont disparu de la configuration"
    for nom in ("stick_droit_x", "stick_droit_y", "stick_gauche_x", "stick_gauche_y"):
        assert nom in document["axes"], f"axe attendu par le téléop absent : {nom}"
