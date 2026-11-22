"""Le schéma du directeur accepte le corpus réel et refuse l'invalide (REQ-ARCH-013).

Le mode `enforce` et le mode `warn` sont testés sans ROS, sur la fonction de
frontière du directeur (REQ-ARCH-014).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "clawbot_common"))
sys.path.insert(0, str(RACINE / "clawbot_director"))

from clawbot_common.validation import validate  # noqa: E402

CORPUS = Path(__file__).resolve().parent / "corpus"

VALIDES = sorted(p for p in CORPUS.glob("*.json") if not p.name.startswith("invalide_"))
INVALIDES = sorted(CORPUS.glob("invalide_*.json"))


@pytest.mark.req("REQ-ARCH-013")
@pytest.mark.parametrize("fichier", VALIDES, ids=[p.stem for p in VALIDES])
def test_corpus_valide(fichier):
    requete = json.loads(fichier.read_text(encoding="utf-8"))["requete"]
    assert validate(requete, "director_command") == [], f"{fichier.name} refusée à tort"


@pytest.mark.req("REQ-ARCH-013")
@pytest.mark.parametrize("fichier", INVALIDES, ids=[p.stem for p in INVALIDES])
def test_requetes_invalides_refusees(fichier):
    requete = json.loads(fichier.read_text(encoding="utf-8"))["requete"]
    assert validate(requete, "director_command"), f"{fichier.name} acceptée à tort"


@pytest.mark.req("REQ-ARCH-013")
def test_le_corpus_couvre_les_cinq_operations():
    operations = {json.loads(p.read_text(encoding="utf-8"))["requete"].get("op") for p in VALIDES}
    assert operations == {"start_skill", "start_sequence", "get_task", "cancel_task", "confirm"}


@pytest.mark.req("REQ-ARCH-013")
def test_le_corpus_vient_des_appelants_reels():
    """Chaque fichier cite son appelant d'origine : le corpus n'est pas inventé."""
    for fichier in VALIDES:
        document = json.loads(fichier.read_text(encoding="utf-8"))
        assert document["appelant"] and ":" in document["appelant"], fichier.name


@pytest.mark.req("REQ-ARCH-014")
def test_mode_enforce_refuse():
    from clawbot_director.validation_frontiere import controler

    erreurs, refus = controler({"op": "op_inconnu"}, mode="enforce")
    assert erreurs
    assert refus == {"ok": False, "error_code": "INVALID_PARAMS",
                     "message": refus["message"]}
    assert refus["message"]


@pytest.mark.req("REQ-ARCH-014")
def test_mode_warn_laisse_passer():
    from clawbot_director.validation_frontiere import controler

    erreurs, refus = controler({"op": "op_inconnu"}, mode="warn")
    assert erreurs, "l'erreur doit être signalée pour le journal"
    assert refus is None, "en warn, la requête suit son cours"


@pytest.mark.req("REQ-ARCH-014")
def test_requete_valide_ne_produit_rien():
    from clawbot_director.validation_frontiere import controler

    assert controler({"op": "get_task"}, mode="enforce") == ([], None)
