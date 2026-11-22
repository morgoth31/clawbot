"""Reprise automatique conforme à la table d'erreurs (REQ-EXEC-011)."""
from __future__ import annotations

import pytest

from clawbot_common.errors import as_json, auto_retry
from clawbot_executive.mission import EtatMission, Etape, Issue, Mission

pytestmark = pytest.mark.req("REQ-EXEC-011")

CODES = sorted(as_json()["codes"] if isinstance(as_json(), dict) else [])


class ExecuteurCompte:
    def __init__(self, code):
        self.code = code
        self.appels = []

    def __call__(self, etape: Etape) -> Issue:
        self.appels.append(etape)
        if etape.skill == "stop":
            return Issue(ok=True)
        return Issue(ok=False, error_code=self.code, message="échec")


@pytest.mark.parametrize("code", CODES)
def test_relance_automatique_conforme_a_la_table(code):
    """Nombre de tentatives et délai observés = ce que dit auto_retry(code)."""
    attendu, delai = auto_retry(code)
    executeur = ExecuteurCompte(code)
    delais: list[float] = []

    def horloge():
        return 0.0

    mission = Mission("m1", "test", [Etape("wait", {})], executeur, horloge=horloge,
                      rapport=lambda i, e, m: {"error_code": i.error_code})
    mission.attendre = lambda d: delais.append(float(d))       # pas d'attente réelle
    mission.run()

    tentatives = max(1, 1 + (1 if attendu else 0))
    assert len([a for a in executeur.appels if a.skill == "wait"]) == tentatives, code
    if attendu:
        assert delais and delais[0] == pytest.approx(delai), code
    else:
        assert delais == [], code
    assert mission.etat == EtatMission.WAITING_DECISION


@pytest.mark.parametrize("code", CODES)
def test_allowed_decisions_recopiees_dans_le_rapport(code):
    from clawbot_common.errors import allowed_decisions

    executeur = ExecuteurCompte(code)
    mission = Mission("m1", "test", [Etape("wait", {})], executeur,
                      rapport=lambda i, e, m: {"error_code": i.error_code,
                                               "allowed_decisions":
                                               list(allowed_decisions(i.error_code))})
    mission.attendre = lambda d: None
    mission.run()
    assert mission.dernier_rapport["allowed_decisions"] == list(allowed_decisions(code))
