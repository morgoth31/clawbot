"""La configuration EKF fixe les cadres et les entrées dont dépend toute la navigation."""
import pathlib

import yaml

CONFIG = pathlib.Path(__file__).resolve().parents[1] / "config" / "ekf.yaml"


def _params():
    return yaml.safe_load(CONFIG.read_text())["ekf_filter_node"]["ros__parameters"]


def test_frames_and_rate():
    node = _params()
    assert node["frequency"] == 30.0
    assert node["two_d_mode"] is True
    assert node["odom_frame"] == "odom"
    assert node["base_link_frame"] == "base_link"
    assert node["world_frame"] == "odom"
    assert node["publish_tf"] is True


def test_inputs_are_the_real_topics():
    node = _params()
    assert node["odom0"] == "/odom_raw"
    assert node["imu0"] == "/imu/data_raw"


def test_velocities_are_fused_not_absolute_pose():
    node = _params()
    odom = node["odom0_config"]
    assert odom[6] is True      # vx
    assert odom[7] is True      # vy : le mecanum se déplace latéralement
    assert odom[11] is True     # vyaw
    assert odom[0] is False     # x absolu : le driver n'en fournit pas
    imu = node["imu0_config"]
    assert imu[11] is True      # vitesse de lacet : compense le glissement Mecanum
    # l'accélération linéaire ne doit pas être fusionnée : biais -> mouvement fantôme à l'arrêt
    assert imu[12] is False
