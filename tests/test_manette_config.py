"""Chargement du YAML de manette : validation nommée, alias, décodage d'axe.

Une configuration fausse doit échouer à la lecture, avec le nom de la clé fautive,
et jamais produire un mapping silencieusement faux.
"""

import math
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "joy_teleop"))

from manette_config import Axe, ConfigInvalide, charger  # noqa: E402

FIXTURE = RACINE / "tests" / "fixtures" / "manette_test.yaml"


def test_charge_un_yaml_valide():
    m = charger(FIXTURE)
    assert m.bouton("home") == 11
    assert m.axe("stick_gauche_x").index == 0


def test_alias_resolu():
    m = charger(FIXTURE)
    assert m.bouton("M1") == m.bouton("A")


def test_bouton_absent_nomme_la_raison():
    m = charger(FIXTURE)
    with pytest.raises(ConfigInvalide) as err:
        m.bouton("T")
    assert "absent" in str(err.value)


def test_cle_manquante_nomme_la_cle(tmp_path):
    chemin = tmp_path / "invalide.yaml"
    chemin.write_text("schema: 1\nappareil: {nom: x}\nboutons: {A: 1}\n", encoding="utf-8")
    with pytest.raises(ConfigInvalide) as err:
        charger(chemin)
    assert "axes" in str(err.value)


def test_schema_inconnu_refuse(tmp_path):
    chemin = tmp_path / "futur.yaml"
    chemin.write_text("schema: 99\n", encoding="utf-8")
    with pytest.raises(ConfigInvalide) as err:
        charger(chemin)
    assert "99" in str(err.value)


def test_fichier_absent_nomme_la_commande(tmp_path):
    with pytest.raises(ConfigInvalide) as err:
        charger(tmp_path / "rien.yaml")
    assert "calibration" in str(err.value)


def test_decode_axe_centre_et_zone_morte():
    a = Axe("x", 0, centre=0.02, minimum=-1.0, maximum=1.0, zone_morte=0.1, inverser=False)
    assert a.decoder(0.02) == 0.0          # au centre
    assert a.decoder(0.08) == 0.0          # dans la zone morte
    assert a.decoder(1.0) == pytest.approx(1.0)
    assert a.decoder(-1.0) == pytest.approx(-1.0)


def test_decode_axe_inverse():
    a = Axe("y", 1, centre=0.0, minimum=-1.0, maximum=1.0, zone_morte=0.1, inverser=True)
    assert a.decoder(1.0) == pytest.approx(-1.0)


def test_decode_borne_a_un():
    a = Axe("x", 0, centre=0.0, minimum=-0.9, maximum=0.9, zone_morte=0.05, inverser=False)
    assert a.decoder(1.0) == pytest.approx(1.0)


def test_nan_vaut_zero():
    a = Axe("x", 0, centre=0.0, minimum=-1.0, maximum=1.0, zone_morte=0.1, inverser=False)
    assert a.decoder(math.nan) == 0.0


def test_valeur_hors_tableau_vaut_zero():
    m = charger(FIXTURE)
    assert m.valeur([], "stick_gauche_x") == 0.0


def test_axe_degenere_refuse_au_chargement(tmp_path):
    chemin = tmp_path / "degenere.yaml"
    chemin.write_text(
        "schema: 1\nappareil: {nom: x}\nboutons: {A: 1}\n"
        "axes:\n  stick_droit_x: {index: 2, centre: 0.0, min: 0.0, max: 0.0, zone_morte: 0.08}\n",
        encoding="utf-8")
    with pytest.raises(ConfigInvalide) as err:
        charger(chemin)
    assert "stick_droit_x" in str(err.value)


def test_appareil_change_de_mode_refuse():
    m = charger(FIXTURE)
    m.appareil["nb_axes"] = 6
    m.appareil["nb_boutons"] = 14
    m.verifier_appareil(6, 14)                     # même forme : accepté
    with pytest.raises(ConfigInvalide) as err:
        m.verifier_appareil(8, 16)                 # descripteur différent
    assert "mode changé" in str(err.value)
