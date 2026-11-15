"""Décodage du format binaire js_event, sans périphérique réel.

Le protocole /dev/input/jsN est décrit dans linux/input.h : struct js_event de
8 octets (u32 time, s16 value, u8 type, u8 number), le bit 0x80 du type marquant
un événement d'initialisation qui annonce les capacités du périphérique.
"""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "joy_teleop"))

from js_lecteur import LecteurJs, decodifier  # noqa: E402


def evenement(valeur, etype, numero, init=False):
    t = etype | (0x80 if init else 0)
    return struct.pack("<IhBB", 0, valeur, t, numero)


def test_axe_normalise():
    l = LecteurJs()
    l.ingerer(evenement(32767, 2, 1))
    assert l.etat().axes[1] == pytest.approx(1.0)


def test_bouton_appuye():
    l = LecteurJs()
    l.ingerer(evenement(1, 1, 6))
    assert l.etat().boutons[6] == 1


def test_evenement_init_compte_la_capacite_sans_transition():
    """JS_EVENT_INIT annonce les axes/boutons : il ne doit pas produire d'état."""
    l = LecteurJs()
    l.ingerer(evenement(0, 2, 0, init=True))
    assert l.etat().axes[0] == 0.0
    assert l.etat().boutons == []


def test_plusieurs_evenements_dans_un_tampon():
    tampon = evenement(1000, 2, 0) + evenement(1, 1, 3)
    l = LecteurJs()
    l.ingerer(tampon)
    assert l.etat().axes[0] == pytest.approx(1000 / 32767)
    assert l.etat().boutons[3] == 1


def test_decodifier_ignore_un_tampon_partiel():
    """Un tampon incomplet ne doit pas lever : on ne décode que les événements entiers."""
    tampon = evenement(5, 2, 0) + b"\x00\x00"
    assert len(decodifier(tampon)) == 1


def test_etat_rend_des_listes_completes():
    l = LecteurJs()
    l.ingerer(evenement(1, 1, 5))
    etat = l.etat()
    assert isinstance(etat.boutons, list)
    assert len(etat.boutons) == 6
    assert etat.boutons[0] == 0
