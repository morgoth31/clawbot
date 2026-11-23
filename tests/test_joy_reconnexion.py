"""REQ-OPS-057 — la manette qui s'endort puis revient ne doit pas exiger un redemarrage.

Le noeud lisait /dev/input/js0 et sortait en code 1 des que le peripherique cessait de rendre
des donnees. Or `ros2 launch` survit a la mort d'un de ses noeuds : l'unite restait
« active » sans publier /joy, et il fallait un `systemctl restart` a la main. La manette
s'endort regulierement, donc le cas est courant.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "joy_teleop"))

import js_joy_source  # noqa: E402


@pytest.mark.req("REQ-OPS-057")
def test_la_manette_est_choisie_parmi_les_interfaces_non_inertielles():
    entrees = [("/dev/input/js0", "Nintendo Switch Pro Controller IMU"),
               ("/dev/input/js1", "Nintendo Switch Pro Controller")]
    assert js_joy_source.choisir_pad(entrees) == (
        "/dev/input/js1", "Nintendo Switch Pro Controller")


@pytest.mark.req("REQ-OPS-057")
def test_aucune_manette_rend_none():
    assert js_joy_source.choisir_pad([]) is None
    assert js_joy_source.choisir_pad([("/dev/input/js0", "… IMU")]) is None


@pytest.mark.req("REQ-OPS-057")
def test_le_numero_de_peripherique_peut_changer():
    """Apres reconnexion, js0 peut devenir js1 : la selection ne doit pas le supposer."""
    entrees = [("/dev/input/js1", "Pro Controller IMU"), ("/dev/input/js2", "Pro Controller")]
    assert js_joy_source.choisir_pad(entrees)[0] == "/dev/input/js2"


@pytest.mark.req("REQ-OPS-057")
def test_la_perte_de_la_manette_ne_termine_plus_le_noeud():
    source = (RACINE / "joy_teleop" / "js_joy_source.py").read_text(encoding="utf-8")
    assert "attente de reconnexion" in source
    assert "manette retrouvée sur" in source
    assert 'ne rend plus de données")\n                return 1' not in source, (
        "la perte du peripherique ne doit plus sortir le noeud en code 1")
