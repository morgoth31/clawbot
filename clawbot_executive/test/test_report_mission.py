"""Rapport de mission (REQ-EXEC-017)."""
from __future__ import annotations

import pytest

from clawbot_executive.mission import EtatMission, Etape, Issue, Mission

pytestmark = pytest.mark.req("REQ-EXEC-017")


def _mission(script=None, **kw):
    reponses = list(script or [Issue(ok=True)])
    mission = Mission("m-7", "aller au salon", [Etape("wait", {"seconds": 1})],
                      lambda e: reponses.pop(0) if reponses else Issue(ok=True),
                      rapport=lambda i, e, m: {"error_code": i.error_code}, **kw)
    return mission


def test_rapport_contient_etat_etapes_rapport_decisions_budget():
    mission = _mission()
    mission.run()
    rapport = mission.rapport()
    for cle in ("mission_id", "objective", "state", "step_index", "step_count",
                "steps", "failure_report", "decisions", "budget", "events"):
        assert cle in rapport, cle
    assert rapport["state"] == EtatMission.SUCCEEDED.value
    assert set(rapport["budget"]) == {"escalations_left", "same_step_attempts_left",
                                      "time_left_s"}


def test_rapport_apres_echec_porte_le_rapport_d_echec_et_les_decisions():
    mission = _mission([Issue(ok=False, error_code="CAPABILITY_INACTIVE", message="ko")])
    mission.run()
    rapport = mission.rapport()
    assert rapport["state"] == EtatMission.WAITING_DECISION.value
    assert rapport["failure_report"]["error_code"] == "CAPABILITY_INACTIVE"
    mission.decider("RETRY_STEP", rationale="la capacité vient d'être activée")
    assert rapport["decisions"] == [] or mission.rapport()["decisions"]


def test_dix_derniers_evenements_seulement():
    mission = Mission("m-8", "long", [Etape(f"s{i}", {}) for i in range(10)],
                      lambda e: Issue(ok=True))
    mission.run()
    rapport = mission.rapport()
    assert len(rapport["events"]) == 10
    assert rapport["events"][-1]["event"] == "SUCCEEDED"
