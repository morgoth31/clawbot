"""Calibration guidée : le résumé doit dire ce qui est mesuré, absent ou suspect.

Le script `calibrer_manette.py` est lancé à la main par l'opérateur ; ce qui est
testé ici est ce qu'il affiche avant d'écrire, et le refus d'écrire un fichier dont
deux noms revendiquent le même code (symptôme d'une séquence décalée).
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "joy_teleop"))

from calibrer_manette import surligner_etat  # noqa: E402
from calibration import Calibration  # noqa: E402


def test_resume_sans_anomalie():
    cal = Calibration(sortie=Path("/dev/null"))
    assert surligner_etat(cal).startswith("✓")


def test_resume_signale_un_absent():
    cal = Calibration(sortie=Path("/dev/null"))
    cal.declarer_entree("light")
    cal.marquer_absent("light", "passée par l'opérateur")
    resume = surligner_etat(cal)
    assert "light" in resume
    assert "absent" in resume


def test_refuse_deux_noms_sur_le_meme_code(tmp_path):
    """Une séquence décalée produit ce symptôme : on refuse d'écrire."""
    cal = Calibration(sortie=tmp_path / "m.yaml")
    cal.enregistrer_bouton("A", 3)
    cal.donnees["boutons"]["B"] = 3          # collision volontaire
    with pytest.raises(RuntimeError) as err:
        cal.ecrire()
    assert "index 3" in str(err.value)
    assert not (tmp_path / "m.yaml").exists()


def test_resume_signale_la_collision():
    cal = Calibration(sortie=Path("/dev/null"))
    cal.enregistrer_bouton("A", 3)
    cal.donnees["boutons"]["B"] = 3
    assert "⚠" in surligner_etat(cal)
