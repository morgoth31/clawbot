"""Machine d'états des missions (REQ-EXEC-010, 012, 013, 015)."""
from __future__ import annotations

import pytest

from clawbot_executive.mission import EtatMission, Etape, Issue, Mission

pytestmark = [pytest.mark.req("REQ-EXEC-010"), pytest.mark.req("REQ-EXEC-012")]


def _req(*identifiants):
    def decorateur(fonction):
        for identifiant in identifiants:
            fonction = pytest.mark.req(identifiant)(fonction)
        return fonction
    return decorateur


class ExecuteurScripte:
    """Faux exécuteur : une réponse par appel, dans l'ordre fourni."""

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels: list[Etape] = []

    def __call__(self, etape: Etape) -> Issue:
        self.appels.append(etape)
        if not self.reponses:
            return Issue(ok=True)
        reponse = self.reponses.pop(0)
        return reponse if isinstance(reponse, Issue) else Issue(ok=bool(reponse))


def _ok():
    return Issue(ok=True)


def _ko(code="TIMEOUT"):
    return Issue(ok=False, error_code=code, message="échec scripté")


def etapes(*noms):
    return [Etape(skill=nom, params={"i": i}) for i, nom in enumerate(noms)]


def test_etapes_dans_l_ordre():
    executeur = ExecuteurScripte([_ok(), _ok(), _ok()])
    mission = Mission("m1", "démo", etapes("wait", "move_relative", "rotate"), executeur)
    mission.run()
    assert mission.etat == EtatMission.SUCCEEDED
    assert [e.skill for e in executeur.appels] == ["wait", "move_relative", "rotate"]


def test_evenement_a_chaque_transition():
    executeur = ExecuteurScripte([_ok(), _ok()])
    mission = Mission("m1", "démo", etapes("wait", "rotate"), executeur)
    mission.run()
    noms = [e["event"] for e in mission.historique]
    assert noms == ["STARTED", "STEP_STARTED", "STEP_SUCCEEDED",
                    "STEP_STARTED", "STEP_SUCCEEDED", "SUCCEEDED"]


def test_echec_persistant_attend_decision():
    # TIMEOUT : relance automatique 1 fois puis échec → WAITING_DECISION
    executeur = ExecuteurScripte([_ko("TIMEOUT"), _ko("TIMEOUT")])
    mission = Mission("m1", "démo", etapes("move_relative"), executeur,
                      rapport=lambda issue, etape, m: {"schema": "clawbot.failure_report/1",
                                                      "error_code": issue.error_code})
    mission.run()
    assert mission.etat == EtatMission.WAITING_DECISION
    assert mission.dernier_rapport["error_code"] == "TIMEOUT"


def test_stop_execute_apres_echec():
    executeur = ExecuteurScripte([_ko("TIMEOUT"), _ko("TIMEOUT")])
    mission = Mission("m1", "démo", etapes("move_relative"), executeur,
                      rapport=lambda i, e, m: {"error_code": i.error_code})
    mission.run()
    assert executeur.appels[-1].skill == "stop"


@pytest.mark.req("REQ-EXEC-013")
def test_decision_hors_table_refusee():
    executeur = ExecuteurScripte([_ko("ESTOP_LATCHED"), _ko("ESTOP_LATCHED")])
    mission = Mission("m1", "démo", etapes("move_relative"), executeur,
                      rapport=lambda i, e, m: {"error_code": i.error_code})
    mission.run()
    avant = mission.escalations_left
    accepte, message = mission.decider("RETRY_STEP", rationale="tentative")
    assert accepte is False and "hors allowed_decisions" in message
    assert mission.escalations_left == avant          # aucun budget consommé


@pytest.mark.req("REQ-EXEC-013")
def test_decision_sans_rationale_refusee():
    executeur = ExecuteurScripte([_ko("SENSOR_STALE"), _ko("SENSOR_STALE")])
    mission = Mission("m1", "démo", etapes("move_relative"), executeur,
                      rapport=lambda i, e, m: {"error_code": i.error_code})
    mission.run()
    accepte, message = mission.decider("RETRY_STEP", rationale="   ")
    assert accepte is False and "rationale" in message


def test_decision_acceptee_consomme_une_escalade_et_reexecute():
    # CAPABILITY_INACTIVE : aucune relance automatique, RETRY_STEP autorisé (table §6.1)
    executeur = ExecuteurScripte([_ko("CAPABILITY_INACTIVE"), _ok()])
    mission = Mission("m1", "démo", etapes("move_relative"), executeur,
                      rapport=lambda i, e, m: {"error_code": i.error_code})
    mission.run()
    accepte, _ = mission.decider("RETRY_STEP", rationale="l'odométrie était bruitée")
    assert accepte
    assert mission.escalations_left == mission.max_escalations - 1
    mission.run()
    assert mission.etat == EtatMission.SUCCEEDED


def test_retry_with_params_change_les_parametres():
    executeur = ExecuteurScripte([_ko("TIMEOUT"), _ko("TIMEOUT"),
                                  _ko("TIMEOUT"), _ko("TIMEOUT"), _ok()])
    mission = Mission("m1", "démo", [Etape("move_relative", {"dx_m": 0.5})], executeur,
                      rapport=lambda i, e, m: {"error_code": i.error_code})
    mission.run()
    accepte, _ = mission.decider("RETRY_WITH_PARAMS", {"dx_m": 0.3}, rationale="raccourcir")
    assert accepte and mission.etapes[0].params["dx_m"] == 0.3


@pytest.mark.req("REQ-EXEC-015")
def test_delai_de_decision_depasse_abandonne():
    horloge = [100.0]
    executeur = ExecuteurScripte([_ko("TIMEOUT"), _ko("TIMEOUT")])
    mission = Mission("m1", "démo", etapes("move_relative"), executeur,
                      horloge=lambda: horloge[0], decision_timeout_s=10.0,
                      rapport=lambda i, e, m: {"error_code": i.error_code})
    mission.run()
    assert mission.etat == EtatMission.WAITING_DECISION
    assert mission.verifier_delai_decision(105.0) is False
    horloge[0] = 111.0
    assert mission.verifier_delai_decision() is True
    assert mission.etat == EtatMission.ABORTED
