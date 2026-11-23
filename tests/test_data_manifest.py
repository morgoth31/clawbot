"""REQ-TEST-020/021 — l'inventaire des jeux de reference est verifiable.

Les donnees vivent sur le robot (`/var/lib/clawbot/test_data`) : un poste sans
enregistrement doit ignorer le test avec une raison explicite, pas echouer.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[1]
INVENTAIRE = RACINE / "tests" / "data_manifest.yaml"

pytestmark = pytest.mark.req("REQ-TEST-021")


def _manifeste() -> dict:
    return yaml.safe_load(INVENTAIRE.read_text(encoding="utf-8"))


def _sha256(chemin: Path) -> str:
    empreinte = hashlib.sha256()
    with chemin.open("rb") as flux:
        for bloc in iter(lambda: flux.read(1 << 20), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


@pytest.mark.req("REQ-TEST-020")
def test_l_inventaire_declare_les_trois_jeux():
    document = _manifeste()
    assert document["dossier"] == "/var/lib/clawbot/test_data"
    # Les trois jeux de REQ-TEST-020 sont obligatoires ; d'autres peuvent s'ajouter.
    obligatoires = {"slam2d_piece", "rgbd_statique", "objets_table"}
    assert obligatoires <= set(document["jeux"]), (
        f"jeux obligatoires absents : {obligatoires - set(document['jeux'])}")
    for nom, jeu in document["jeux"].items():
        assert jeu["topics"], f"{nom} : aucun topic declare"


def test_les_fichiers_de_reference_correspondent_a_l_inventaire():
    document = _manifeste()
    dossier = Path(document["dossier"])
    if not dossier.is_dir():
        pytest.skip("données de référence absentes : voir F00")

    manquants, absents = [], []
    for nom, jeu in document["jeux"].items():
        if not jeu.get("enregistre"):
            absents.append(nom)
            continue
        for fichier in jeu.get("fichiers", []):
            chemin = dossier / fichier["nom"]
            if not chemin.is_file():
                manquants.append(fichier["nom"])
                continue
            assert fichier["taille_octets"] == chemin.stat().st_size, fichier["nom"]
            assert fichier["sha256"] == _sha256(chemin), fichier["nom"]
            assert fichier["duree_s"] > 0
        assert jeu.get("verites_terrain"), (
            f"{nom} : les mesures au mètre ruban sont la vérité terrain, elles manquent")

    assert not manquants, f"fichiers inventoriés mais absents : {manquants}"
    if absents:
        pytest.skip(f"jeux pas encore enregistrés : {', '.join(absents)} (voir F00 §4.2)")
