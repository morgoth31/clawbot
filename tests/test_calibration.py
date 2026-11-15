"""Procédure de calibration : squelette, écriture atomique, refus d'un YAML incomplet.

Une entrée déclarée doit être soit mesurée, soit aliasée, soit explicitement
absente. Aucun fichier n'est écrit tant que ce n'est pas le cas : un YAML partiel
produirait un mapping silencieusement faux au prochain démarrage du robot.
"""

import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "joy_teleop"))

from calibration import Calibration  # noqa: E402


def test_refuse_ecriture_si_entree_declaree_non_traitee(tmp_path):
    cal = Calibration(sortie=tmp_path / "manette.yaml")
    cal.declarer_entree("A")
    cal.declarer_entree("home")
    cal.enregistrer_bouton("A", 1)          # home reste non traité
    with pytest.raises(RuntimeError) as err:
        cal.ecrire()
    assert "home" in str(err.value)
    assert not (tmp_path / "manette.yaml").exists()


def test_ecriture_atomique(tmp_path):
    cal = Calibration(sortie=tmp_path / "manette.yaml")
    cal.declarer_entree("A")
    cal.enregistrer_bouton("A", 1)
    cal.ecrire()
    contenu = yaml.safe_load((tmp_path / "manette.yaml").read_text(encoding="utf-8"))
    assert contenu["boutons"]["A"] == 1
    assert contenu["schema"] == 1
    assert contenu["outil"] == "joy_teleop/calibration.py"
    assert not (tmp_path / "manette.yaml.tmp").exists()


def test_alias_detecte():
    cal = Calibration(sortie=Path("/dev/null"))
    cal.declarer_entree("A")
    cal.declarer_entree("M1")
    cal.enregistrer_bouton("A", 1)
    cal.enregistrer_bouton("M1", 1)          # même code → alias, pas un doublon
    assert cal.donnees["aliases"]["M1"] == "A"
    assert "M1" not in cal.donnees["boutons"]


def test_absent_leve_l_exigence_mais_se_voit():
    cal = Calibration(sortie=Path("/dev/null"))
    cal.declarer_entree("light")
    cal.marquer_absent("light", "délai de 25 s dépassé sans événement")
    assert "light" in cal.donnees["absents"]
    cal.ecrire_sans_fichier()               # ne doit pas lever


def test_sauvegarde_de_l_ancien_fichier(tmp_path):
    sortie = tmp_path / "manette.yaml"
    sortie.write_text("schema: 1\nancien: vrai\n", encoding="utf-8")
    cal = Calibration(sortie=sortie)
    cal.declarer_entree("A")
    cal.enregistrer_bouton("A", 1)
    cal.ecrire()
    sauvegardes = list(tmp_path.glob("manette.yaml.bak-*"))
    assert len(sauvegardes) == 1
    assert "ancien" in sauvegardes[0].read_text(encoding="utf-8")
