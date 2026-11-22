"""Journal JSONL d'une mission (REQ-EXEC-016)."""
from __future__ import annotations

import json

import pytest

from clawbot_executive.journal import Journal

pytestmark = pytest.mark.req("REQ-EXEC-016")


def test_chemin_date_et_mission(tmp_path):
    journal = Journal("m-42", dossier=tmp_path, date="2026-11-22")
    journal.ecrire("STARTED", {"objective": "démo"})
    attendu = tmp_path / "2026-11-22" / "m-42.jsonl"
    assert attendu.is_file(), list(tmp_path.rglob("*"))


def test_une_ligne_json_valide_par_evenement(tmp_path):
    journal = Journal("m-1", dossier=tmp_path, date="2026-11-22")
    for nom in ("STARTED", "STEP_STARTED", "STEP_SUCCEEDED", "SUCCEEDED"):
        journal.ecrire(nom, {"i": 1})
    journal.fermer()
    lignes = journal.relire()
    assert [ligne["event"] for ligne in lignes] == ["STARTED", "STEP_STARTED",
                                                    "STEP_SUCCEEDED", "SUCCEEDED"]
    assert all(isinstance(ligne["detail"], dict) for ligne in lignes)


def test_aucune_image_dans_le_journal(tmp_path):
    journal = Journal("m-1", dossier=tmp_path, date="2026-11-22")
    journal.ecrire("STEP_SUCCEEDED", {"path": "/var/lib/clawbot/snapshots/x.jpg",
                                      "image": b"\xff\xd8\xff" * 1000,
                                      "detail": {"data": "A" * 5000}})
    entree = journal.relire()[0]
    assert entree["detail"]["path"].endswith(".jpg")
    assert "retiré" in entree["detail"]["image"]
    assert "retiré" in entree["detail"]["detail"]["data"]
    assert len(json.dumps(entree)) < 4000


def test_fichier_ferme_en_fin_de_mission(tmp_path):
    journal = Journal("m-1", dossier=tmp_path, date="2026-11-22")
    journal.ecrire("STARTED")
    journal.fermer()
    assert journal._flux is None
    journal.ecrire("SUCCEEDED")            # rouvre sans erreur
    journal.fermer()
    assert len(journal.relire()) == 2
