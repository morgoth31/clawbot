"""Manifeste des capacités : contenu attendu et validation (REQ-CAPA-001, REQ-OPS-030)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
MANIFESTE = RACINE / "clawbot_capabilities" / "config" / "capabilities.yaml"

pytestmark = pytest.mark.req("REQ-CAPA-001")


def test_le_manifeste_decrit_les_neuf_capacites():
    from clawbot_capabilities.manifeste import charger

    manifeste = charger(MANIFESTE)
    assert list(manifeste) == [
        "base", "lidar", "mapping", "navigation", "arm",
        "wrist_vision", "depth_vision", "detection", "voice",
    ]


def test_mapping_est_une_unite_systemd_pas_un_script():
    """INV-08 : le pilotage passe par systemd, pas par un `ros2 launch` lancé à la main."""
    from clawbot_capabilities.manifeste import charger

    mapping = charger(MANIFESTE)["mapping"]
    assert mapping.units == ["clawbot-slam.service"]
    assert all(u.endswith(".service") for c in charger(MANIFESTE).values() for u in c.units)


def test_conflits_symetriques():
    from clawbot_capabilities.manifeste import charger

    manifeste = charger(MANIFESTE)
    for nom, capacite in manifeste.items():
        for autre in capacite.conflicts:
            assert nom in manifeste[autre].conflicts, (nom, autre)


def test_always_on_est_base_et_lidar():
    from clawbot_capabilities.manifeste import charger

    manifeste = charger(MANIFESTE)
    assert {n for n, c in manifeste.items() if c.always_on} == {"base", "lidar"}


def test_chaque_capacite_geree_a_un_ready_when():
    from clawbot_capabilities.manifeste import charger

    for nom, capacite in charger(MANIFESTE).items():
        if capacite.managed:
            assert capacite.ready_when, f"{nom} sans condition de disponibilité"


def test_ready_when_rejette_un_champ_inconnu(tmp_path):
    from clawbot_capabilities.manifeste import ErreurManifeste, charger

    mauvais = {"capacites": {"base": {
        "units": ["base.service"], "managed": True,
        "ready_when": [{"topic": "/odom", "vitesse": 3}],
    }}}
    chemin = tmp_path / "m.yaml"
    chemin.write_text(yaml.safe_dump(mauvais), encoding="utf-8")
    with pytest.raises(ErreurManifeste, match="champ inconnu"):
        charger(chemin)


def test_requires_inconnu_rejete(tmp_path):
    from clawbot_capabilities.manifeste import ErreurManifeste, charger

    mauvais = {"capacites": {"base": {
        "units": ["base.service"], "managed": True, "requires": ["hyperdrive"],
        "ready_when": [{"topic": "/odom", "min_hz": 8.0}],
    }}}
    chemin = tmp_path / "m.yaml"
    chemin.write_text(yaml.safe_dump(mauvais), encoding="utf-8")
    with pytest.raises(ErreurManifeste, match="inconnue"):
        charger(chemin)


def test_etat_initial_du_manifeste():
    """Toutes les capacités démarrent INACTIVE sauf les always_on, laissées au démarrage."""
    from clawbot_capabilities.controleur import Controleur, Etat
    from clawbot_capabilities.manifeste import charger

    controleur = Controleur(charger(MANIFESTE), backend=None, fabrique_sondes=lambda c: [],
                            horloge=lambda: 0.0)
    assert controleur.etiquette("navigation") == Etat.INACTIVE
    assert controleur.etiquette("base") == Etat.INACTIVE
