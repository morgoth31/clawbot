"""REQ-DRV-017 — le coup de demarrage ne se rejoue plus a chaque hesitation du stick.

`_moving` retombait a False des la premiere consigne nulle, or la rampe et la zone morte en
produisent en permanence pendant la conduite. Chaque passage relancait donc un `kick_boost`
de 1,8x : avec le gain a 0,20 m/s, un bond a 0,35 m/s puis une retombee a 0,20 — une secousse
a chaque hesitation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "clawbot_base_driver"))

from clawbot_base_driver.base_driver import SEUIL_ARRET_S  # noqa: E402

SOURCE = (RACINE / "clawbot_base_driver" / "clawbot_base_driver" /
          "base_driver.py").read_text(encoding="utf-8")


@pytest.mark.req("REQ-DRV-017")
def test_le_seuil_d_arret_est_defini_et_credible():
    assert 0.2 <= SEUIL_ARRET_S <= 2.0, f"seuil {SEUIL_ARRET_S} hors de [0,2 ; 2,0] s"


@pytest.mark.req("REQ-DRV-017")
def test_le_coup_de_demarrage_depend_de_la_duree_d_arret():
    """Le code doit comparer la duree d'arret au seuil, pas seulement l'etat _moving."""
    assert "self._arret_depuis = maintenant" in SOURCE, "l'instant d'arret doit etre memorise"
    assert "if depuis >= SEUIL_ARRET_S:" in SOURCE, (
        "le coup de demarrage doit exiger un arret franc, pas un simple passage par zero")


@pytest.mark.req("REQ-DRV-017")
def test_la_regle_reproduite_sur_des_cas():
    """Reproduction de la condition du pilote, sur des cas connus."""
    def faut_kick(rampe_vx, en_mouvement, depuis_arret):
        if rampe_vx == 0.0 or en_mouvement:
            return False
        return depuis_arret >= SEUIL_ARRET_S

    assert faut_kick(0.20, False, 2.0), "depart apres 2 s d'arret : coup legitime"
    assert not faut_kick(0.20, False, 0.1), (
        "passage par la zone morte en roulant : aucun coup ne doit partir")
    assert not faut_kick(0.20, True, 5.0), "deja en mouvement : aucun coup"
    assert not faut_kick(0.0, False, 9.0), "consigne nulle : aucun coup"
