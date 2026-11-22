"""Chaîne complète en domaine 99 : skill_server + arbitre + base simulée (P08).

On vérifie ce qui sort vraiment : `/cmd_vel/skill` est publié par le skill, l'arbitre
le relaie sur `/cmd_vel_safe`, `fake_base` l'intègre en `/odom`, et le skill mesure
sa distance sur cette odométrie. L'e-stop en cours de route doit arrêter le skill.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

if os.environ.get("ROS_DOMAIN_ID") != "99":
    pytest.skip("test d'intégration : domaine 99 requis", allow_module_level=True)

RACINE = Path(__file__).resolve().parents[2]
for paquet in ("clawbot_safety", "clawbot_sim", "clawbot_executive"):
    sys.path.insert(0, str(RACINE / paquet))

import rclpy  # noqa: E402
from geometry_msgs.msg import Twist  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy  # noqa: E402
from std_msgs.msg import Bool, String  # noqa: E402

from clawbot_interfaces.action import ExecuteSkill  # noqa: E402
from clawbot_safety.arbitrator import Arbitrator  # noqa: E402
from clawbot_sim.fake_base import FakeBase  # noqa: E402
from clawbot_sim.fake_inputs import FakeInputs  # noqa: E402

from clawbot_executive.serveur import ServeurSkills  # noqa: E402

REGISTRE = RACINE / "clawbot_executive" / "config" / "skills.yaml"

pytestmark = [pytest.mark.integration, pytest.mark.req("REQ-EXEC-007"),
              pytest.mark.req("REQ-EXEC-004")]


class Banc:
    def __init__(self):
        self.executeur = SingleThreadedExecutor()
        self.arbitre = Arbitrator()
        self.base = FakeBase()
        self.entrees = FakeInputs()
        self.espion = Node("espion_p08")
        self.cmd_safe: list[Twist] = []
        self.safety: list[dict] = []
        self.espion.create_subscription(Twist, "/cmd_vel_safe",
                                        lambda m: self.cmd_safe.append(m), 10)
        self.espion.create_subscription(String, "/safety/state",
                                        lambda m: self.safety.append(json.loads(m.data)), 10)
        qos_capa = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                              durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.pub_capa = self.espion.create_publisher(String, "/clawbot/capabilities/state", qos_capa)
        qos_estop = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                               durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.pub_estop = self.espion.create_publisher(Bool, "/safety/estop", qos_estop)
        for noeud in (self.arbitre, self.base, self.entrees, self.espion):
            self.executeur.add_node(noeud)

        self.serveur = ServeurSkills(registre=REGISTRE, demarrer=True)
        self.client = ActionClient(self.espion, ExecuteSkill, "/clawbot/execute_skill")

    def publier_capacites(self) -> None:
        message = String()
        message.data = json.dumps({"capabilities": [
            {"name": "base", "state": "ACTIVE", "units": [], "requires": [],
             "conflicts": [], "stale_flows": []},
            {"name": "lidar", "state": "ACTIVE", "units": [], "requires": ["base"],
             "conflicts": [], "stale_flows": []},
        ]})
        self.pub_capa.publish(message)

    def tourner(self, duree_s: float) -> None:
        fin = time.monotonic() + duree_s
        while time.monotonic() < fin:
            self.publier_capacites()
            self.executeur.spin_once(timeout_sec=0.02)

    def fermer(self) -> None:
        self.serveur.destroy_node()
        for noeud in (self.arbitre, self.base, self.entrees, self.espion):
            noeud.destroy_node()
        self.executeur.shutdown()


@pytest.fixture(scope="module")
def banc():
    if not rclpy.ok():
        rclpy.init()
    banc = Banc()
    assert banc.client.wait_for_server(timeout_sec=20.0), "serveur d'action injoignable"
    banc.tourner(2.0)                       # découverte + capacités ACTIVE
    yield banc
    banc.fermer()


def _envoyer(banc, nom, params, timeout_s=0.0):
    goal = ExecuteSkill.Goal()
    goal.mission_id = "integration"
    goal.skill = nom
    goal.params_json = json.dumps(params)
    goal.timeout_s = timeout_s
    futur = banc.client.send_goal_async(goal)
    attente(banc, futur)
    return futur.result()


def attente(banc, futur, limite_s=45.0):
    fin = time.monotonic() + limite_s
    while not futur.done() and time.monotonic() < fin:
        banc.tourner(0.05)
    assert futur.done(), "futur non résolu"


def _resultat(banc, handle, limite_s=60.0):
    futur = handle.get_result_async()
    attente(banc, futur, limite_s)
    return futur.result()


def test_move_relative_atteint_la_cible(banc):
    depart = (banc.base.x, banc.base.y)
    handle = _envoyer(banc, "move_relative", {"dx_m": 0.5, "max_speed_mps": 0.2})
    assert handle.accepted
    resultat = _resultat(banc, handle).result
    distance = ((banc.base.x - depart[0]) ** 2 + (banc.base.y - depart[1]) ** 2) ** 0.5
    assert resultat.outcome == ExecuteSkill.Result.OUTCOME_SUCCEEDED, resultat.message
    assert distance == pytest.approx(0.5, abs=0.05), f"distance parcourue {distance:.3f} m"


def test_rotate_atteint_l_angle(banc):
    depart = banc.base.yaw
    handle = _envoyer(banc, "rotate", {"angle_rad": 1.5708, "max_speed_rps": 0.8})
    assert handle.accepted
    resultat = _resultat(banc, handle).result
    ecart = banc.base.yaw - depart
    assert resultat.outcome == ExecuteSkill.Result.OUTCOME_SUCCEEDED, resultat.message
    assert abs(ecart - 1.5708) < 0.0873, f"rotation {ecart:.3f} rad"   # ±5°


def test_estop_pendant_le_deplacement(banc):
    handle = _envoyer(banc, "move_relative", {"dx_m": 1.5, "max_speed_mps": 0.2})
    assert handle.accepted
    banc.tourner(1.0)                       # le robot avance
    assert any(m.linear.x != 0.0 for m in banc.cmd_safe[-20:]), "le skill n'a rien publié"

    banc.pub_estop.publish(Bool(data=True))
    resultat = _resultat(banc, handle).result
    assert resultat.outcome == ExecuteSkill.Result.OUTCOME_FAILED
    assert resultat.error_code == "ESTOP_LATCHED", resultat.error_code
    banc.tourner(0.5)
    assert banc.cmd_safe[-1].linear.x == 0.0 and banc.cmd_safe[-1].angular.z == 0.0
    assert resultat.failure_report_json, "rapport d'échec absent"
