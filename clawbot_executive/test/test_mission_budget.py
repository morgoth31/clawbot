"""Budgets de §6.3 (REQ-EXEC-014)."""
from __future__ import annotations

import pytest

from clawbot_executive.mission import (DUREE_DEFAUT_S, PLAFOND_DUREE_S,
                                       PLAFOND_ESCALADES, EtatMission, Etape, Issue, Mission)

pytestmark = pytest.mark.req("REQ-EXEC-014")


class ToujoursEnEchec:
    def __call__(self, etape: Etape) -> Issue:
        if etape.skill == "stop":
            return Issue(ok=True)
        return Issue(ok=False, error_code="TIMEOUT", message="échec")


def mission(duree=DUREE_DEFAUT_S, escalades=PLAFOND_ESCALADES, horloge=None):
    mission = Mission("m1", "test", [Etape("wait", {})], ToujoursEnEchec(),
                      horloge=horloge or (lambda: 0.0), max_duration_s=duree,
                      max_escalations=escalades,
                      rapport=lambda i, e, m: {"error_code": i.error_code})
    mission.attendre = lambda d: None
    return mission


def test_quatrieme_escalade_refusee_et_abandon():
    """TIMEOUT autorise RETRY_WITH_PARAMS : chaque décision change les paramètres."""
    m = mission()
    m.run()
    for tentative in range(PLAFOND_ESCALADES):
        accepte, message = m.decider("RETRY_WITH_PARAMS", {"i": tentative},
                                     rationale="nouvelle approche")
        assert accepte, message
        m.run()
    accepte, message = m.decider("RETRY_WITH_PARAMS", {"i": 99}, rationale="une de trop")
    assert accepte is False
    assert "plus d'escalade" in message
    assert m.etat == EtatMission.ABORTED


def test_tentatives_epuisees_refusent_retry_step():
    """§6.3 : 2 tentatives au total pour un même couple étape/paramètres."""
    m = mission()
    m.run()                                     # tentative 1 + relance auto = 2
    assert m.attempts[Etape("wait", {}).cle()] == 2

    # SENSOR_STALE : RETRY_STEP autorisé par la table, mais le plafond de tentatives l'emporte
    m.dernier_rapport["error_code"] = "SENSOR_STALE"
    avant = m.escalations_left
    accepte, message = m.decider("RETRY_STEP", rationale="encore une")
    assert accepte is False
    assert "tentatives épuisées" in message
    assert m.escalations_left == avant          # refus gratuit


def test_retry_with_params_ouvre_une_nouvelle_tentative():
    """D'autres paramètres = une autre clé, donc le plafond ne s'applique pas."""
    m = mission()
    m.run()
    avant = m.escalations_left
    accepte, message = m.decider("RETRY_WITH_PARAMS", {"i": 99}, rationale="autre approche")
    assert accepte, message
    assert m.escalations_left == avant - 1


def test_duree_maximale_depassee():
    horloge = [0.0]

    class Lente:
        def __call__(self, etape: Etape) -> Issue:
            horloge[0] += 700.0
            return Issue(ok=True)

    m = Mission("m1", "test", [Etape("wait", {}), Etape("rotate", {})], Lente(),
                horloge=lambda: horloge[0], max_duration_s=600.0)
    m.run()
    assert m.etat == EtatMission.ABORTED


def test_plafonnement_des_parametres_de_goal():
    m = Mission("m1", "test", [Etape("wait", {})], lambda e: Issue(ok=True),
                max_duration_s=99999.0, max_escalations=99)
    assert m.max_duration_s == PLAFOND_DUREE_S
    assert m.max_escalations == PLAFOND_ESCALADES


def test_une_a_vingt_etapes():
    with pytest.raises(ValueError):
        Mission("m1", "test", [], lambda e: Issue(ok=True))
    with pytest.raises(ValueError):
        Mission("m1", "test", [Etape("wait", {})] * 21, lambda e: Issue(ok=True))
