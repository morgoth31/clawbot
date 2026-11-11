"""Machine d'attention : IDLE -> WATCHING -> ENGAGED, hystérésis et cooldowns.

Logique pure, horloge injectée. Elle ne décide pas de la confiance ni de la distance (c'est le
nœud, qui voit les capteurs) : elle décide **quand** une transition mérite de réveiller S2.
Un seul réveil par transition, jamais en continu.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_sentinel.attention import ENGAGED, IDLE, WATCHING, Attention, Regles  # noqa: E402


class Horloge:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def avancer(self, secondes):
        self.t += secondes


def _types(evenements):
    return [e["type"] for e in evenements]


def test_premiere_frame_met_en_veille_sans_reveiller():
    horloge = Horloge()
    a = Attention(clock=horloge)

    evenements = a.voir(True)
    assert a.etat == WATCHING
    assert _types(evenements) == ["ETAT"]
    assert evenements[0]["state"] == WATCHING


def test_deuxieme_frame_consecutive_engage_et_reveille_une_fois():
    horloge = Horloge()
    a = Attention(clock=horloge)
    a.voir(True)
    horloge.avancer(1.0)

    evenements = a.voir(True)
    assert a.etat == ENGAGED
    reveils = [e for e in evenements if e["type"] == "REVEIL"]
    assert len(reveils) == 1 and reveils[0]["source"] == "VISUAL_PERSON"


def test_une_frame_manquee_casse_la_consecutivite():
    horloge = Horloge()
    a = Attention(clock=horloge)
    a.voir(True)
    a.voir(False)
    horloge.avancer(1.0)

    a.voir(True)
    assert a.etat == WATCHING, "deux frames consecutives exigees, pas deux frames cumulees"


def test_cooldown_visuel_empeche_un_second_reveil_rapproche():
    horloge = Horloge()
    a = Attention(Regles(absence_s=1.0, cooldown_visuel_s=60.0), clock=horloge)
    a.voir(True)
    a.voir(True)                      # reveil 1
    a.voir(False)
    horloge.avancer(2.0)              # absence -> IDLE
    a.voir(True)
    evenements = a.voir(True)         # re-engagement dans le cooldown
    assert a.etat == ENGAGED
    assert not [e for e in evenements if e["type"] == "REVEIL"]


def test_absence_prolongee_ramene_en_veille():
    horloge = Horloge()
    a = Attention(Regles(absence_s=10.0), clock=horloge)
    a.voir(True)
    a.voir(True)
    assert a.etat == ENGAGED

    horloge.avancer(5.0)
    a.voir(False)
    assert a.etat == ENGAGED, "une frame manquee ne suffit pas"

    horloge.avancer(6.0)
    evenements = a.voir(False)
    assert a.etat == IDLE
    assert evenements[-1]["state"] == IDLE


def test_audio_reveille_avec_son_propre_cooldown():
    horloge = Horloge()
    a = Attention(Regles(cooldown_audio_s=5.0), clock=horloge)

    evenements = a.entendre(True)
    assert [e["source"] for e in evenements if e["type"] == "REVEIL"] == ["AUDIO_VAD"]
    assert a.etat == ENGAGED

    horloge.avancer(1.0)
    assert not [e for e in a.entendre(True) if e["type"] == "REVEIL"]
    horloge.avancer(5.0)
    assert [e["source"] for e in a.entendre(True) if e["type"] == "REVEIL"] == ["AUDIO_VAD"]


def test_absence_de_signal_n_emet_aucun_evenement():
    a = Attention()
    assert a.voir(False) == []
    assert a.entendre(False) == []
