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

from calibration import Calibration, compter_appuis  # noqa: E402


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


# ── Phase gâchettes ──────────────────────────────────────────────────────────

class FauxLecteurGachette:
    """Scènes (boutons pressés, axes) pour mesurer si un axe bouge pendant l'appui."""

    def __init__(self, scenes):
        self.scenes = list(scenes)
        self.rang = 0

    def lire(self, attente=0.02):
        return True

    def etat(self):
        from js_lecteur import Etat
        appuis, axes = self.scenes[min(self.rang, len(self.scenes) - 1)]
        self.rang += 1
        boutons = [0] * 14
        for i in appuis:
            boutons[i] = 1
        return Etat(axes=list(axes), boutons=boutons)


def test_gachette_binaire_detectee():
    """Aucun axe ne bouge pendant l'appui : la gâchette est binaire."""
    cal = Calibration(sortie=Path("/dev/null"))
    cal.enregistrer_bouton("L", 7)
    lecteur = FauxLecteurGachette([([], [0.0] * 6), ([7], [0.0] * 6), ([], [0.0] * 6)])
    cal.phase_gachettes(lecteur, entrees=[("L", "la gâchette L")],
                        delai_s=0.05, journal=lambda *a, **k: None)
    assert cal.donnees["capacites"]["gachettes_analogiques"]["disponible"] is False
    assert "aucun axe" in cal.donnees["capacites"]["gachettes_analogiques"]["raison"]


def test_gachette_analogique_detectee():
    cal = Calibration(sortie=Path("/dev/null"))
    cal.enregistrer_bouton("L", 7)
    lecteur = FauxLecteurGachette([
        ([], [0.0] * 6),
        ([7], [0.0, 0.0, 0.0, 0.0, 0.9, 0.0]),   # un axe bouge de 0.9
        ([], [0.0] * 6),
    ])
    cal.phase_gachettes(lecteur, entrees=[("L", "la gâchette L")],
                        delai_s=0.05, journal=lambda *a, **k: None)
    cap = cal.donnees["capacites"]["gachettes_analogiques"]
    assert cap["disponible"] is True
    assert cap["axes_detectes"]


# ── Validations exigées par la calibration réelle du 2026-11-15 ─────────────

def test_axe_jamais_balaye_refuse(tmp_path):
    """stick_droit_x avait min = max = 0 : l'axe n'avait pas bougé."""
    cal = Calibration(sortie=tmp_path / "m.yaml")
    cal.enregistrer_axe("stick_droit_x", index=2, centre=0.0, minimum=0.0,
                        maximum=0.0, zone_morte=0.08, inverser=False)
    with pytest.raises(RuntimeError) as err:
        cal.ecrire()
    assert "stick_droit_x" in str(err.value)
    assert not (tmp_path / "m.yaml").exists()


def test_reserve_ne_bloque_pas_l_ecriture(tmp_path):
    """T commute peut-être un mode : ce n'est pas un bouton, mais ce n'est pas un oubli."""
    cal = Calibration(sortie=tmp_path / "m.yaml")
    cal.declarer_entree("T")
    cal.declarer_reserve("T", "aucun événement : commutateur de mode probable")
    cal.ecrire()
    contenu = yaml.safe_load((tmp_path / "m.yaml").read_text(encoding="utf-8"))
    assert contenu["reserve"]["T"].startswith("aucun événement")


def test_gachette_enregistree_par_nom(tmp_path):
    cal = Calibration(sortie=tmp_path / "m.yaml")
    cal.enregistrer_gachette("ZL", analogique=True, axes={"6": [0.0, 1.0]})
    cal.enregistrer_gachette("L", analogique=False)
    cal.ecrire()
    contenu = yaml.safe_load((tmp_path / "m.yaml").read_text(encoding="utf-8"))
    assert contenu["gachettes"]["ZL"]["analogique"] is True
    assert contenu["gachettes"]["L"]["analogique"] is False


# ── Phase actionneurs ────────────────────────────────────────────────────────

def test_actionneurs_sans_led_ni_confirmation(tmp_path):
    cal = Calibration(sortie=Path("/dev/null"))
    (tmp_path / "ff").write_text("107030000 0", encoding="utf-8")
    cal.phase_actionneurs(chemin_ff=tmp_path / "ff", base_hid=tmp_path,
                          demander=lambda q: False, vibrer=lambda: None,
                          journal=lambda *a, **k: None)
    cap = cal.donnees["capacites"]
    assert cap["vibration"]["disponible"] is True
    assert cap["vibration"]["verifie"] is False       # l'opérateur n'a rien senti
    assert cap["lumieres"]["disponible"] is False
    assert "leds" in cap["lumieres"]["raison"]


def test_actionneurs_led_exposee(tmp_path):
    cal = Calibration(sortie=Path("/dev/null"))
    (tmp_path / "ff").write_text("0", encoding="utf-8")
    (tmp_path / "leds" / "nintendo_player1").mkdir(parents=True)
    cal.phase_actionneurs(chemin_ff=tmp_path / "ff", base_hid=tmp_path,
                          demander=lambda q: True, vibrer=None,
                          journal=lambda *a, **k: None)
    cap = cal.donnees["capacites"]
    assert cap["vibration"]["disponible"] is False
    assert cap["lumieres"]["disponible"] is True


# ── CLI et garde-fous ────────────────────────────────────────────────────────

def test_cli_refuse_si_teleop_active(monkeypatch, tmp_path):
    import calibration
    monkeypatch.setattr(calibration, "_teleop_active", lambda *a, **k: True)
    code = calibration.main(["--sortie", str(tmp_path / "x.yaml"), "--seulement", "axes"])
    assert code == 3
    assert not (tmp_path / "x.yaml").exists()


def test_cli_refuse_sans_manette(monkeypatch, tmp_path):
    import calibration
    monkeypatch.setattr(calibration, "_teleop_active", lambda *a, **k: False)
    monkeypatch.setattr(calibration, "lister_manettes", lambda: [])
    code = calibration.main(["--sortie", str(tmp_path / "x.yaml"), "--seulement", "axes"])
    assert code == 4


def test_reponse_oui_est_comprise():
    import calibration
    assert calibration.reponse_booleenne("o") is True
    assert calibration.reponse_booleenne("Oui") is True
    assert calibration.reponse_booleenne("n") is False
    assert calibration.reponse_booleenne("") is False


# ── Turbo (bouton T) ────────────────────────────────────────────────────────

class FauxLecteurRafale:
    """Rejoue un motif d'appuis sur un index : 1,0,1,0… pour simuler le turbo."""

    def __init__(self, motif, index=3):
        self.motif = motif
        self.index = index
        self.rang = 0

    def lire(self, attente=0.02):
        return True

    def etat(self):
        from js_lecteur import Etat
        valeur = self.motif[min(self.rang, len(self.motif) - 1)]
        self.rang += 1
        boutons = [0] * 14
        boutons[self.index] = valeur
        return Etat(axes=[0.0] * 6, boutons=boutons)


def test_compte_les_appuis_d_un_mainien_unique():
    lecteur = FauxLecteurRafale([0, 1, 1, 1, 1, 0])
    assert compter_appuis(lecteur, 3, 0.12) == 1


def test_compte_les_appuis_d_une_rafale_turbo():
    lecteur = FauxLecteurRafale([0, 1, 0, 1, 0, 1, 0, 1])
    assert compter_appuis(lecteur, 3, 0.16) >= 3


def test_turbo_enregistre(tmp_path):
    cal = Calibration(sortie=tmp_path / "m.yaml")
    cal.enregistrer_turbo(bouton="T", actif=True, repetitions=6,
                          reference="A", duree_s=2.0)
    cal.ecrire()
    contenu = yaml.safe_load((tmp_path / "m.yaml").read_text(encoding="utf-8"))
    assert contenu["capacites"]["turbo"]["actif"] is True
    assert contenu["capacites"]["turbo"]["repetitions"] == 6
