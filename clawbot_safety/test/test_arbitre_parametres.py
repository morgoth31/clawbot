"""Seuils et table d'entrées en paramètres ROS en lecture seule (REQ-OPS-020)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from clawbot_safety import arbitrator  # noqa: E402
from soutien_arbitre import contexte, fermer, parametre_lecture_seule  # noqa: E402

NOMS = [
    "publish_rate_hz",
    "stale_s",
    "cmd_timeout_s",
    "inputs.names",
    "inputs.teleop.topic", "inputs.teleop.priority", "inputs.teleop.timeout_s",
    "inputs.nav.topic", "inputs.nav.priority", "inputs.nav.timeout_s",
    "inputs.skill.topic", "inputs.skill.priority", "inputs.skill.timeout_s",
]


@pytest.fixture
def arbitre():
    ctx = contexte()
    node = arbitrator.Arbitrator(context=ctx)
    yield node
    fermer(node, ctx)


@pytest.mark.req("REQ-OPS-020")
@pytest.mark.parametrize("nom", NOMS)
def test_parametre_declare_en_lecture_seule(arbitre, nom):
    assert arbitre.has_parameter(nom), f"{nom} non déclaré"
    assert parametre_lecture_seule(arbitre, nom), f"{nom} devrait être read_only"


@pytest.mark.req("REQ-OPS-020")
def test_valeurs_par_defaut_de_la_table(arbitre):
    assert arbitre.get_parameter("publish_rate_hz").value == 20.0
    assert arbitre.get_parameter("stale_s").value == 2.0
    assert arbitre.get_parameter("cmd_timeout_s").value == 0.5
    assert arbitre.get_parameter("inputs.teleop.topic").value == "/cmd_vel/teleop"
    assert arbitre.get_parameter("inputs.teleop.priority").value == 100
    assert arbitre.get_parameter("inputs.nav.priority").value == 50
    assert arbitre.get_parameter("inputs.skill.priority").value == 40
    # P14 (REQ-OPS-044) : l'entree `legacy` /cmd_vel est retiree, aucun editeur ne la
    # publie plus. Trois entrees, pas quatre.
    assert [n for n in arbitre.get_parameter("inputs.names").value] == [
        "teleop", "nav", "skill"]


@pytest.mark.req("REQ-OPS-020")
def test_yaml_de_configuration_coherent():
    """Le YAML du dépôt décrit la même table que les valeurs par défaut."""
    chemin = RACINE / "clawbot_safety" / "config" / "arbitrator.yaml"
    assert chemin.is_file(), "clawbot_safety/config/arbitrator.yaml manquant"
    doc = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    params = doc["safety_arbitrator"]["ros__parameters"]

    assert params["publish_rate_hz"] == 20.0
    for nom in params["inputs"]["names"]:
        entree = params["inputs"][nom]
        assert {"topic", "priority", "timeout_s"} <= set(entree)
    assert params["inputs"]["teleop"]["priority"] == 100
    assert "legacy" not in params["inputs"], "l'entree legacy est retiree (REQ-OPS-044)"
    assert set(params["inputs"]["names"]) == {"teleop", "nav", "skill"}
