"""Capacités et garde-fous avant mouvement (REQ-EXEC-002)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.req("REQ-EXEC-002")


def etats(actives=("base", "lidar")):
    from clawbot_executive.etats import Etats

    etats = Etats()
    etats.capacites = {nom: {"name": nom, "state": "ACTIVE"} for nom in actives}
    etats.safety_state = "OK"
    etats.estop_latched = False
    return etats


def test_capacite_inactive_refuse():
    from clawbot_executive.skills import MoveRelative
    from clawbot_executive.registre import Definition

    skill = MoveRelative(Definition(nom="move_relative", description="", params_schema={},
                                    requires=["base", "lidar"], timeout_s=30.0,
                                    bornes={"max_speed_mps": 0.2, "max_distance_m": 2.0}))
    assert skill.check_preconditions(etats(actives=("base",))) == "CAPABILITY_INACTIVE"
    assert skill.check_preconditions(etats()) is None


def test_capacite_inactive_nomme_la_capacite():
    from clawbot_executive.skills import MoveRelative
    from clawbot_executive.registre import Definition

    skill = MoveRelative(Definition(nom="move_relative", description="", params_schema={},
                                    requires=["base", "lidar"], timeout_s=30.0, bornes={}))
    assert "lidar" in skill.detail_precondition(etats(actives=("base",)))


def test_safety_bloquant_avant_mouvement():
    from clawbot_executive.deplacement import code_safety

    assert code_safety(safety_state="OK", estop_latched=False) is None
    assert code_safety(safety_state="ESTOP_LATCHED", estop_latched=True) == "ESTOP_LATCHED"
    assert code_safety(safety_state="SENSOR_STALE", estop_latched=False) == "SENSOR_STALE"
    assert code_safety(safety_state="HOLD", estop_latched=False) == "SAFETY_HOLD"
    assert code_safety(safety_state="OK", estop_latched=True) == "ESTOP_LATCHED"
