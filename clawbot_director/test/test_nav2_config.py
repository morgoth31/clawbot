"""Cohérence de la configuration Nav2 avec le catalogue et avec les mesures du robot.

Ces tests ne lancent pas Nav2 : ils vérifient ce qu'un fichier de paramètres peut casser sans
bruit — charger la mauvaise carte, viser une tolérance plus large que le critère de sortie du lot,
ou demander des vitesses que la base ne sait pas tenir.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_director import waypoints  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
PARAMS = RACINE / "config" / "nav2_clawbot.yaml"
LAUNCH = RACINE / "launch" / "navigation.launch.py"

# Mesures de la session du 2026-11-11 (ETAT-PROJET.md §2) : consigne 0,10 m/s -> 0,102 m/s.
VITESSE_LINEAIRE_MESUREE = 0.10


@pytest.fixture(scope="module")
def params():
    return yaml.safe_load(PARAMS.read_text(encoding="utf-8"))


def test_la_carte_chargee_est_celle_du_catalogue(params):
    catalogue = waypoints.charger()
    chargee = Path(params["map_server"]["ros__parameters"]["yaml_filename"])
    assert chargee == RACINE / "maps" / f"{catalogue.carte}.yaml"
    assert chargee.is_file(), f"carte absente : {chargee}"
    # la résolution retenue pour les waypoints doit être celle du fichier de carte
    meta = yaml.safe_load(chargee.read_text(encoding="utf-8"))
    assert meta["resolution"] == pytest.approx(0.05)



def test_les_cadres_sont_ceux_du_robot(params):
    assert params["amcl"]["ros__parameters"]["global_frame_id"] == "map"
    assert params["amcl"]["ros__parameters"]["base_frame_id"] == "base_link"
    assert params["amcl"]["ros__parameters"]["odom_frame_id"] == "odom"
    assert params["bt_navigator"]["ros__parameters"]["global_frame"] == "map"
    assert params["bt_navigator"]["ros__parameters"]["robot_base_frame"] == "base_link"
    assert params["bt_navigator"]["ros__parameters"]["odom_topic"] == "/odom"
    global_costmap = params["global_costmap"]["global_costmap"]["ros__parameters"]
    assert global_costmap["global_frame"] == "map"
    assert global_costmap["robot_base_frame"] == "base_link"
    local_costmap = params["local_costmap"]["local_costmap"]["ros__parameters"]
    assert local_costmap["global_frame"] == "odom"
    assert params["map_server"]["ros__parameters"]["use_sim_time"] is False



def test_la_tolerance_d_arrivee_est_sous_le_critere_du_lot(params):
    tolerance = params["controller_server"]["ros__parameters"]["general_goal_checker"][
        "xy_goal_tolerance"]
    assert tolerance <= 0.20, "le critere de sortie est ±0,20 m : la tolerance doit etre plus fine"


def test_les_vitesses_demandees_sont_tenables(params):
    noeud = params["velocity_smoother"]["ros__parameters"]
    assert noeud["max_velocity"][0] <= VITESSE_LINEAIRE_MESUREE + 1e-9
    poursuite = params["controller_server"]["ros__parameters"]["FollowPath"]
    assert poursuite["desired_linear_vel"] <= VITESSE_LINEAIRE_MESUREE


def test_l_amcl_demarre_sur_un_waypoint_du_catalogue(params):
    pose = params["amcl"]["ros__parameters"]["initial_pose"]
    depart = waypoints.charger().resoudre("ouest")
    ecart = math.hypot(pose["x"] - depart.x, pose["y"] - depart.y)
    assert ecart <= 0.20, \
        "la pose initiale supposee doit etre un waypoint connu, sinon la premiere navigation ment"



def test_le_rayon_du_chassis_correspond_au_robot(params):
    rayon = params["global_costmap"]["global_costmap"]["ros__parameters"]["robot_radius"]
    assert 0.12 <= rayon <= 0.18, f"rayon {rayon} m incompatible avec un chassis de 20 cm"


def test_le_fichier_de_lancement_lit_la_carte_du_catalogue():
    assert LAUNCH.is_file()
    texte = LAUNCH.read_text(encoding="utf-8")
    assert "waypoints.yaml" in texte, "le lancement doit deduire la carte du catalogue"
    assert "slam" in texte and "False" in texte, "AMCL et SLAM Toolbox ne doivent pas coexister"
