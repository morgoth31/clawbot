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


# ── Phase boutons ────────────────────────────────────────────────────────────

class FauxLecteur:
    """Rejoue une suite d'états : chaque appel à etat() rend la scène suivante."""

    def __init__(self, scenes):
        self.scenes = list(scenes)
        self.rang = 0

    def lire(self, attente=0.02):
        return True

    def etat(self):
        from js_lecteur import Etat
        appuis = self.scenes[min(self.rang, len(self.scenes) - 1)] if self.scenes else []
        self.rang += 1
        boutons = [0] * 14
        for i in appuis:
            boutons[i] = 1
        return Etat(axes=[0.0] * 6, boutons=boutons)


def test_phase_boutons_mesure_alias_et_home():
    cal = Calibration(sortie=Path("/dev/null"))
    # une scène vide sert de référence, puis un appui : A=1, M1=1 (alias), home=11
    lecteur = FauxLecteur([[], [1], [], [1], [], [11]])
    cal.phase_boutons(
        lecteur,
        entrees=[("A", "le bouton A"), ("M1", "le bouton M1"), ("home", "le bouton Home")],
        delai_s=1.0,
        journal=lambda *a, **k: None,
    )
    assert cal.donnees["boutons"]["A"] == 1
    assert cal.donnees["boutons"]["home"] == 11
    assert cal.donnees["aliases"]["M1"] == "A"
    assert "M1" not in cal.donnees["boutons"]


def test_phase_boutons_marque_absent_apres_delai():
    cal = Calibration(sortie=Path("/dev/null"))
    lecteur = FauxLecteur([[]])          # aucun appui, jamais
    cal.phase_boutons(
        lecteur,
        entrees=[("light", "le bouton lumière")],
        delai_s=0.05,
        journal=lambda *a, **k: None,
    )
    assert "light" in cal.donnees["absents"]
    assert "délai" in cal.donnees["absents_raisons"]["light"]


# ── Phase axes ───────────────────────────────────────────────────────────────

class FauxLecteurAxes:
    """Rejoue une suite de vecteurs d'axes : chaque etat() rend la scène suivante."""

    def __init__(self, scenes):
        self.scenes = list(scenes)
        self.rang = 0

    def lire(self, attente=0.02):
        return True

    def etat(self):
        from js_lecteur import Etat
        scene = self.scenes[min(self.rang, len(self.scenes) - 1)] if self.scenes else [0.0] * 6
        self.rang += 1
        return Etat(axes=list(scene), boutons=[0] * 14)


def test_phase_axes_centre_debattement_et_sens_horizontal():
    cal = Calibration(sortie=Path("/dev/null"))
    scenes = [
        [0.02, 0.0, 0.0, 0.0, 0.0, 0.0], [0.02, 0.0, 0.0, 0.0, 0.0, 0.0],   # repos
        [-0.99, 0.0, 0.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],   # balayage
        [1.0, 0.0, 0.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],     # extrême droite
    ]
    cal.phase_axes(
        FauxLecteurAxes(scenes),
        axes=[("stick_gauche_x", 0, "droite", "le stick gauche à droite")],
        duree_repos=0.04, duree_balayage=0.04, duree_extreme=0.04,
        journal=lambda *a, **k: None,
    )
    a = cal.donnees["axes"]["stick_gauche_x"]
    assert a["index"] == 0
    assert a["centre"] == pytest.approx(0.02)
    assert a["min"] == pytest.approx(-0.99)
    assert a["max"] == pytest.approx(1.0)
    assert a["inverser"] is False        # positive à droite : pas d'inversion
    assert a["zone_morte"] >= 0.08       # plancher


def test_phase_axes_sens_vertical_inverse():
    """Sur ce pad, le haut donne une valeur NÉGATIVE : la config doit l'enregistrer."""
    cal = Calibration(sortie=Path("/dev/null"))
    scenes = [
        [0.0, -0.01, 0.0, 0.0, 0.0, 0.0], [0.0, -0.01, 0.0, 0.0, 0.0, 0.0],
        [0.0, -0.99, 0.0, 0.0, 0.0, 0.0], [0.0, 0.99, 0.0, 0.0, 0.0, 0.0],
        [0.0, -1.0, 0.0, 0.0, 0.0, 0.0], [0.0, -1.0, 0.0, 0.0, 0.0, 0.0],
    ]
    cal.phase_axes(
        FauxLecteurAxes(scenes),
        axes=[("stick_gauche_y", 1, "haut", "le stick gauche en haut")],
        duree_repos=0.04, duree_balayage=0.04, duree_extreme=0.04,
        journal=lambda *a, **k: None,
    )
    assert cal.donnees["axes"]["stick_gauche_y"]["inverser"] is True
