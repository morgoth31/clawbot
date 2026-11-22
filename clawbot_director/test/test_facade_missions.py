"""Façade du directeur : `op` → mission, et mode par défaut (REQ-EXEC-018)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from clawbot_director.facade import traduire

pytestmark = pytest.mark.req("REQ-EXEC-018")

RACINE = Path(__file__).resolve().parents[2]
CORPUS = RACINE / "clawbot_director" / "test" / "corpus"


def corpus():
    """Le corpus P06 enveloppe la requête réelle sous la clé « requete »."""
    fichiers = sorted(CORPUS.glob("*.json"))
    assert fichiers, f"corpus absent : {CORPUS}"
    entrees = []
    for fichier in fichiers:
        document = json.loads(fichier.read_text(encoding="utf-8"))
        entrees.append((fichier.name, document.get("requete", document)))
    return entrees


def test_start_skill_devient_une_mission_d_une_etape():
    mission = traduire({"op": "start_skill", "skill": "move_relative",
                        "args": {"dx_m": 0.5}})
    assert mission == [{"skill": "move_relative", "params": {"dx_m": 0.5}}]


def test_start_sequence_devient_la_suite_d_etapes():
    mission = traduire({"op": "start_sequence", "steps": [
        {"skill": "wait", "args": {"seconds": 1}},
        {"skill": "capture_image", "args": {"camera": "wrist"}},
    ]})
    assert [e["skill"] for e in mission] == ["wait", "capture_image"]
    assert mission[0]["params"] == {"seconds": 1}


@pytest.mark.parametrize("op", ["get_task", "cancel_task", "confirm", "inconnu"])
def test_operations_sans_equivalent_restent_historiques(op):
    assert traduire({"op": op}) is None


def test_requetes_invalides_ne_produisent_pas_de_mission():
    assert traduire(None) is None
    assert traduire({}) is None
    assert traduire({"op": "start_skill"}) is None                     # skill absent
    assert traduire({"op": "start_skill", "skill": "wait", "args": "x"}) is None
    assert traduire({"op": "start_sequence", "steps": []}) is None
    assert traduire({"op": "start_sequence", "steps": [{"skill": "wait"}] * 21}) is None


def test_corpus_p06_traduit_ou_reste_historique():
    """Chaque requête réelle du corpus a une issue explicite, sans exception."""
    conversions = 0
    for nom, document in corpus():
        mission = traduire(document)
        if document.get("op") in ("start_skill", "start_sequence") and mission is not None:
            conversions += 1
            assert all("skill" in etape and "params" in etape for etape in mission), nom
        elif mission is not None:
            raise AssertionError(f"{nom} aurait dû rester historique")
    assert conversions >= 1, "aucune requête du corpus convertie : la façade ne sert à rien"


def test_mode_legacy_par_defaut():
    """Le passage en `mission` est une décision opérateur : le défaut ne bouge pas."""
    source = (RACINE / "clawbot_director" / "clawbot_director" / "director_node.py").read_text(
        encoding="utf-8")
    assert 'declare_parameter("facade_mode"' in source
    assert 'get_parameter("facade_mode").value' in source
    index = source.index('declare_parameter("facade_mode"')
    extrait = source[index:index + 200]
    assert '"legacy"' in extrait, extrait
