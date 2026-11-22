"""Arrêt d'urgence verrouillé (P04, REQ-SAFETY-012/013)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from std_msgs.msg import Bool
from std_srvs.srv import Trigger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from clawbot_safety import arbitrator  # noqa: E402
from soutien_arbitre import capteurs_sains, contexte, fermer, twist  # noqa: E402


@pytest.fixture
def arbitre():
    ctx = contexte()
    node = arbitrator.Arbitrator(context=ctx)
    yield node
    fermer(node, ctx)


def tick_a(arb, t):
    capteurs_sains(arb, t)
    arb.tick()
    return arb.derniere_sortie


@pytest.mark.req("REQ-SAFETY-012")
def test_estop_annule_au_tick_suivant(arbitre):
    """Un true sur /safety/estop annule la sortie au tick suivant, sans attendre."""
    t = 1000.0
    arbitre._on_input("teleop", twist(0.20))
    assert tick_a(arbitre, t) == (0.20, 0.0, 0.0)

    arbitre._on_estop(Bool(data=True))
    sortie = tick_a(arbitre, t + 0.05)          # un seul tick plus tard (50 ms)

    assert sortie == (0.0, 0.0, 0.0)
    assert arbitre.etat["estop_latched"] is True
    assert arbitre.etat["state"] == "ESTOP_LATCHED"


@pytest.mark.req("REQ-SAFETY-012")
def test_verrou_survit_a_estop_false(arbitre):
    """Le retour à false ne relâche pas le verrou : seul un réarmement le fait."""
    t = 1000.0
    arbitre._on_estop(Bool(data=True))
    tick_a(arbitre, t)
    arbitre._on_estop(Bool(data=False))
    arbitre._on_input("teleop", twist(0.20))

    sortie = tick_a(arbitre, t + 0.10)
    assert sortie == (0.0, 0.0, 0.0)
    assert arbitre.etat["estop_latched"] is True


@pytest.mark.req("REQ-SAFETY-013")
def test_rearmement_refuse_tant_que_estop_est_true(arbitre):
    """Tant que le signal est encore true, le réarmement est refusé."""
    t = 1000.0
    arbitre._on_estop(Bool(data=True))
    tick_a(arbitre, t)

    reponse = Trigger.Response()
    arbitre._sur_reset_estop(Trigger.Request(), reponse)

    assert reponse.success is False
    assert arbitre.etat["estop_latched"] is True


@pytest.mark.req("REQ-SAFETY-013")
def test_rearmement_accepte_apres_retour_a_false(arbitre):
    """Signal retombé : le service lève le verrou et la sortie repart."""
    t = 1000.0
    arbitre._on_estop(Bool(data=True))
    tick_a(arbitre, t)
    arbitre._on_estop(Bool(data=False))

    reponse = Trigger.Response()
    arbitre._sur_reset_estop(Trigger.Request(), reponse)
    assert reponse.success is True

    arbitre._on_input("teleop", twist(0.20))
    assert tick_a(arbitre, t + 0.20) == (0.20, 0.0, 0.0)
    assert arbitre.etat["estop_latched"] is False


@pytest.mark.req("REQ-SAFETY-013")
def test_service_sans_estop_actif_repond_false(arbitre):
    """Réarmer quand rien n'est verrouillé ne prétend pas avoir agi."""
    reponse = Trigger.Response()
    arbitre._sur_reset_estop(Trigger.Request(), reponse)
    assert reponse.success is False
