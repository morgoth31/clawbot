"""Arrêt des moteurs sur silence des consignes (P03, REQ-DRV-002).

Trois comportements, une horloge simulée : l'arrêt tombe dans la fenêtre
[0,30 s ; 0,35 s], il n'est émis qu'une fois, et une consigne nulle qui arrive
normalement ne déclenche aucune alerte.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from geometry_msgs.msg import Twist

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from clawbot_base_driver import base_driver  # noqa: E402
from soutien_pilote import (FausseHorloge, FauxJournal, FauxRosmaster, arreter,  # noqa: E402
                            instancier)


@pytest.fixture
def pilote(tmp_path, monkeypatch):
    # le pilote en service tient /run/lock/clawbot-mcu.lock : verrou temporaire
    monkeypatch.setattr(base_driver, "chemin_verrou",
                        lambda: str(tmp_path / "clawbot-mcu.lock"))
    faux = FauxRosmaster()
    horloge = FausseHorloge()
    journal = FauxJournal()
    node, contexte = instancier(base_driver, faux, horloge, journal)
    yield node, faux, horloge, journal
    arreter(node, contexte)


def _consigne(node, vx):
    msg = Twist()
    msg.linear.x = vx
    node.cmd_vel_callback(msg)


@pytest.mark.req("REQ-DRV-002")
def test_arret_sur_silence(pilote):
    """Un zéro est envoyé au MCU entre 0,30 et 0,35 s après la dernière consigne."""
    node, faux, horloge, _journal = pilote

    _consigne(node, 0.1)
    assert faux.appels and faux.appels[-1] != (0.0, 0.0, 0.0), "la consigne doit partir"

    horloge.avance(0.29)
    node._surveiller_silence()
    assert faux.appels[-1] != (0.0, 0.0, 0.0), "trop tôt : le délai de 0,3 s n'est pas écoulé"

    horloge.avance(0.04)          # 0,33 s
    node._surveiller_silence()
    assert faux.appels[-1] == (0.0, 0.0, 0.0), "le zéro doit être envoyé avant 0,35 s"


@pytest.mark.req("REQ-DRV-002")
def test_pas_de_rafale_de_zero(pilote):
    """Après l'arrêt, 2 s de silence ne produisent qu'un seul appel nul."""
    node, faux, horloge, _journal = pilote

    _consigne(node, 0.1)
    horloge.avance(0.31)
    node._surveiller_silence()
    assert faux.appels[-1] == (0.0, 0.0, 0.0)

    zeros = sum(1 for appel in faux.appels if appel == (0.0, 0.0, 0.0))
    for _ in range(40):            # 2 s à 20 Hz
        horloge.avance(0.05)
        node._surveiller_silence()
    assert sum(1 for appel in faux.appels if appel == (0.0, 0.0, 0.0)) == zeros == 1


@pytest.mark.req("REQ-DRV-002")
def test_consigne_nulle_continue(pilote):
    """Des consignes nulles reçues à 20 Hz ne déclenchent pas d'alerte."""
    node, _faux, horloge, journal = pilote

    for _ in range(20):            # 1 s de consignes nulles
        _consigne(node, 0.0)
        horloge.avance(0.05)
        node._surveiller_silence()

    assert journal.avertissements == [], f"alerte injustifiée : {journal.avertissements}"
