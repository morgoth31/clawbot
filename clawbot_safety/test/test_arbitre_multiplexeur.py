"""Multiplexeur à priorités de l'arbitre (P04, REQ-SAFETY-010/011/015)."""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from clawbot_safety import arbitrator  # noqa: E402
from soutien_arbitre import capteurs_sains, contexte, fermer, twist  # noqa: E402

ENTREES = {"teleop": 100, "nav": 50, "skill": 40, "legacy": 10}
PAIRES = list(itertools.combinations(ENTREES, 2))


@pytest.fixture
def arbitre():
    ctx = contexte()
    node = arbitrator.Arbitrator(context=ctx)
    yield node
    fermer(node, ctx)


def tick_a(arb, t):
    """Alimente les capteurs puis exécute un tick à l'instant t."""
    capteurs_sains(arb, t)
    arb.tick()
    return arb.derniere_sortie


@pytest.mark.req("REQ-SAFETY-010")
@pytest.mark.parametrize("basse,haute", PAIRES, ids=[f"{b}<{h}" for b, h in PAIRES])
def test_priorite_entre_entrees(arbitre, basse, haute):
    """Entre deux entrées fraîches, la priorité la plus haute commande."""
    t = 1000.0
    arbitre._on_input(basse, twist(0.05))
    arbitre._on_input(haute, twist(0.30))
    sortie = tick_a(arbitre, t)

    assert sortie == (0.30, 0.0, 0.0), f"{haute} (priorité {ENTREES[haute]}) doit gagner"
    assert arbitre.etat["source"] == haute


@pytest.mark.req("REQ-SAFETY-010")
def test_entree_plus_prioritaire_gagne_apres_une_autre(arbitre):
    """L'ordre d'arrivée ne compte pas : teleop l'emporte même s'il arrive après skill."""
    t = 1000.0
    arbitre._on_input("skill", twist(0.30))
    tick_a(arbitre, t)
    assert arbitre.etat["source"] == "skill"

    arbitre._on_input("teleop", twist(0.05))
    sortie = tick_a(arbitre, t + 0.05)
    assert sortie == (0.05, 0.0, 0.0)
    assert arbitre.etat["source"] == "teleop"


@pytest.mark.req("REQ-SAFETY-011")
def test_entree_expiree_bascule_sur_la_suivante(arbitre):
    """Passé son timeout_s (0,5 s), l'entrée prioritaire est ignorée."""
    t = 1000.0
    arbitre._on_input("teleop", twist(0.05))
    arbitre._on_input("nav", twist(0.30))
    tick_a(arbitre, t)
    assert arbitre.etat["source"] == "teleop"

    # teleop se tait ; nav continue d'émettre
    for i in range(1, 20):
        arbitre._on_input("nav", twist(0.30))
        sortie = tick_a(arbitre, t + 0.05 * i)

    assert sortie == (0.30, 0.0, 0.0)
    assert arbitre.etat["source"] == "nav"


@pytest.mark.req("REQ-SAFETY-011")
def test_aucune_entree_valide_sortie_nulle(arbitre):
    """Sans aucune entrée fraîche, la sortie est nulle et la source inconnue."""
    sortie = tick_a(arbitre, 1000.0)
    assert sortie == (0.0, 0.0, 0.0)
    assert arbitre.etat["source"] is None


@pytest.mark.req("REQ-SAFETY-015")
def test_etat_contient_les_champs_anciens_et_nouveaux(arbitre):
    """Le champ d'état garde son sens ; les trois champs nouveaux sont présents."""
    t = 1000.0
    arbitre._on_input("teleop", twist(0.05))
    tick_a(arbitre, t)

    charge = arbitre.etat          # la charge exacte publiée sur /safety/state
    assert charge["state"] == "OK", "la valeur d'état doit rester celle d'avant"
    assert charge["source"] == "teleop"
    assert charge["estop_latched"] is False
    assert isinstance(charge["max_callback_ms"], float)
    assert charge["max_callback_ms"] >= 0.0
