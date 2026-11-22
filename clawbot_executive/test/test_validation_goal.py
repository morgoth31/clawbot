"""Schéma des paramètres : refus avant tout mouvement (REQ-EXEC-001)."""
from __future__ import annotations

from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
REGISTRE = RACINE / "clawbot_executive" / "config" / "skills.yaml"

pytestmark = pytest.mark.req("REQ-EXEC-001")


@pytest.fixture(scope="module")
def definitions():
    from clawbot_executive.registre import charger

    return charger(REGISTRE)


def test_le_registre_declare_les_skills_du_prompt(definitions):
    assert set(definitions) == {
        "stop", "wait", "move_relative", "rotate", "capture_image", "navigate_to", "save_map",
    }


def test_chaque_skill_a_un_schema_et_une_description(definitions):
    for nom, definition in definitions.items():
        assert definition.params_schema["type"] == "object", nom
        assert definition.params_schema.get("additionalProperties") is False, nom
        assert definition.description, nom


@pytest.mark.parametrize("params", [
    {"dx_m": 5.0},                       # au-delà de 2,0 m
    {"dx_m": 0.5, "max_speed_mps": 0.9},  # au-delà de 0,2 m/s
    {"dx_m": "loin"},                    # type faux
    {"dy_m": 0.2},                       # dx_m manquant
    {"dx_m": 0.2, "teleport": True},      # propriété inconnue
])
def test_move_relative_refuse_les_parametres_hors_bornes(definitions, params):
    from clawbot_executive.registre import valider_parametres

    erreurs = valider_parametres(definitions["move_relative"], params)
    assert erreurs, f"{params} aurait dû être refusé"


def test_move_relative_accepte_une_consigne_valide(definitions):
    from clawbot_executive.registre import valider_parametres

    assert valider_parametres(definitions["move_relative"], {"dx_m": 0.5}) == []


@pytest.mark.parametrize("params", [
    {"angle_rad": 7.0},                    # au-delà de 2π
    {"angle_rad": 1.0, "max_speed_rps": 2.0},
])
def test_rotate_refuse_les_parametres_hors_bornes(definitions, params):
    from clawbot_executive.registre import valider_parametres

    assert valider_parametres(definitions["rotate"], params), params


def test_wait_borne_a_30_secondes(definitions):
    from clawbot_executive.registre import valider_parametres

    assert valider_parametres(definitions["wait"], {"seconds": 31}) != []
    assert valider_parametres(definitions["wait"], {"seconds": 0}) != []
    assert valider_parametres(definitions["wait"], {"seconds": 2}) == []


def test_save_map_nom_restreint(definitions):
    from clawbot_executive.registre import valider_parametres

    assert valider_parametres(definitions["save_map"], {"name": "salon"}) == []
    assert valider_parametres(definitions["save_map"], {"name": "../../etc/passwd"}) != []


def test_bornes_du_registre_sous_les_limites_du_pilote(definitions):
    """Bornes validées par l'opérateur le 2026-11-22 (pilote : 1,0 / 1,0 / 5,0)."""
    assert definitions["move_relative"].bornes["max_speed_mps"] == pytest.approx(0.2)
    assert definitions["move_relative"].bornes["max_distance_m"] == pytest.approx(2.0)
    assert definitions["rotate"].bornes["max_speed_rps"] == pytest.approx(0.8)
    assert definitions["rotate"].bornes["max_angle_rad"] == pytest.approx(6.283185, rel=1e-5)
