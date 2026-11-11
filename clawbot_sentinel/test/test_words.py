"""Mots d'arrêt locaux et oui/non conditionnel — logique pure, sans ROS.

« stop », « arrête-toi », « halte » coupent toujours, sans S2 et sans réseau. « oui » et « non »
ne sont consommés que si le directeur est en WAITING_CONFIRMATION : ailleurs ils appartiennent à
la phrase (« non, l'autre tasse »).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_sentinel.words import STOP, OUI, NON, intention  # noqa: E402


def test_mots_d_arret_reconnus_avec_ponctuation_et_accents():
    for phrase in ("stop", "STOP !", "arrête-toi", "Arrête toi.", "halte", "arrêt"):
        assert intention(phrase) == STOP, phrase


def test_un_mot_qui_contient_stop_ne_declenche_pas():
    assert intention("le stopwatch tourne") is None
    assert intention("stoppe la musique") is None


def test_oui_et_non_reconnus_seuls():
    assert intention("oui") == OUI
    assert intention("Oui, vas-y.") == OUI
    assert intention("non") == NON
    assert intention("Non, l'autre tasse") == NON


def test_phrase_sans_intention_locale():
    assert intention("prends la tasse rouge") is None
    assert intention("") is None
    assert intention("   ") is None


def test_l_arret_prime_sur_tout_le_reste():
    assert intention("non, stop") == STOP
