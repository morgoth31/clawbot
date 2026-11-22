"""Source unique des joints et manifeste de la capacité `arm` (REQ-ARM-001, 002).

Deux propriétés, vérifiables sans robot :

  - `/joint_states` n'a qu'un éditeur : `joint_state_publisher`, dont la source est
    `/arm/joint_states` ; le pilote ne déclare plus d'éditeur mort sur ce topic ;
  - le manifeste de capacités nomme les vraies unités et les vraies actions du bras,
    et sonde `/arm/joint_states` à 8 Hz.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "clawbot_capabilities"))

from clawbot_capabilities.manifeste import charger  # noqa: E402

PILOTE = RACINE / "clawbot_base_driver" / "clawbot_base_driver" / "base_driver.py"
LAUNCH = RACINE / "clawbot_bringup" / "launch" / "description.launch.py"
MANIFESTE = RACINE / "clawbot_capabilities" / "config" / "capabilities.yaml"


@pytest.mark.req("REQ-ARM-001")
def test_le_pilote_ne_declare_aucun_editeur_sur_joint_states():
    source = PILOTE.read_text(encoding="utf-8")
    assert "create_publisher(JointState, \"joint_states\"" not in source
    assert "create_publisher(JointState, 'joint_states'" not in source
    # Le message JointState reste importé pour d'éventuels abonnements : ce n'est pas
    # l'import qui compte, c'est l'éditeur déclaré et jamais publié (P01-M13).
    assert "staPublisher" not in source


@pytest.mark.req("REQ-ARM-001")
def test_joint_state_publisher_est_la_seule_source_du_bras():
    source = LAUNCH.read_text(encoding="utf-8")
    # Le fichier de lancement passe les parametres par un dict Python.
    assert 'source_list=["/arm/joint_states"]' in source
    assert "rate=20.0" in source
    # Deux éditeurs sur /joint_states se contrediraient : le launch ne doit lancer que
    # robot_state_publisher et joint_state_publisher.
    assert source.count('executable="robot_state_publisher"') == 1
    assert source.count('executable="joint_state_publisher"') == 1


@pytest.mark.req("REQ-ARM-002")
def test_manifeste_arm_nomme_les_unites_et_actions_reelles():
    manifeste = charger(MANIFESTE)
    capacite = manifeste["arm"]

    assert set(capacite.units) == {"clawbot-arm-controller.service",
                                   "clawbot-move-group.service"}
    assert capacite.managed is True
    actions = {condition["action"] for condition in capacite.ready_when if "action" in condition}
    # P13 : les skills du bras passent par MoveIt, qui planifie puis execute sur le
    # controleur ; la capacite ne doit etre active que si les trois servent.
    assert "/move_action" in actions
    assert "/arm_controller/follow_joint_trajectory" in actions
    assert "/grip_controller/follow_joint_trajectory" in actions
    cadences = {condition["topic"]: condition.get("min_hz")
                for condition in capacite.ready_when if "topic" in condition}
    assert cadences.get("/arm/joint_states") == 8.0


@pytest.mark.req("REQ-ARM-006")
def test_le_controleur_demarre_sur_la_pose_de_repos():
    """L'hypothèse de position initiale doit être la pose validée, sinon saut au 1er goal."""
    import yaml

    parametres = yaml.safe_load(
        (RACINE / "clawbot_arm_controller" / "config" / "arm_controller.yaml")
        .read_text(encoding="utf-8"))["arm_trajectory_server"]["ros__parameters"]
    attendu = [0.0, 1.570796, -1.570796, -1.570796, 0.0]

    assert parametres["initial_positions"] == pytest.approx(attendu, abs=1e-5)
    # -0,265222 rad sur la pince = servo 6 à 149°, la demi-fermeture de la pose de repos.
    assert parametres["initial_grip_position"] == pytest.approx(-0.265222, abs=1e-5)
