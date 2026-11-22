"""Exécutif de mission en domaine 99 : réussite, échec, décision (P09).

Chaîne réelle : exécutif → skill_server → arbitre → fake_base → odom. Le scénario
d'échec bloque la base simulée pour obtenir un TIMEOUT, puis une décision
RETRY_WITH_PARAMS relance la mission.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

if os.environ.get("ROS_DOMAIN_ID") != "99":
    pytest.skip("test d'intégration : domaine 99 requis", allow_module_level=True)

RACINE = Path(__file__).resolve().parents[2]
for paquet in ("clawbot_safety", "clawbot_sim", "clawbot_executive"):
    sys.path.insert(0, str(RACINE / paquet))

import rclpy  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy  # noqa: E402
from sensor_msgs.msg import Image  # noqa: E402
from std_msgs.msg import Int32MultiArray, String  # noqa: E402

from clawbot_interfaces.action import ExecuteMission  # noqa: E402
from clawbot_interfaces.srv import GetMissionReport, SubmitDecision  # noqa: E402
from clawbot_safety.arbitrator import Arbitrator  # noqa: E402
from clawbot_sim.fake_base import FakeBase  # noqa: E402
from clawbot_sim.fake_inputs import FakeInputs  # noqa: E402

from clawbot_executive.mission_node import MissionExecutive  # noqa: E402
from clawbot_executive.serveur import ServeurSkills  # noqa: E402

REGISTRE = RACINE / "clawbot_executive" / "config" / "skills.yaml"

pytestmark = [pytest.mark.integration, pytest.mark.req("REQ-EXEC-010"),
              pytest.mark.req("REQ-EXEC-012")]


class Banc:
    def __init__(self, journal_dir: Path):
        self.executeur = SingleThreadedExecutor()
        self.arbitre = Arbitrator()
        self.base = FakeBase()
        self.entrees = FakeInputs()
        self.espion = Node("espion_p09")
        self.pub_capa = self.espion.create_publisher(
            String, "/clawbot/capabilities/state",
            QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                       durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.pub_image = self.espion.create_publisher(Image, "/wrist_camera/image_raw", 5)
        # Pilote réel : /arm/servo_angles à 10 Hz. Sans ce flux, `move_relative` est
        # refusé ARM_NOT_AT_REST (REQ-ARM-004) — le banc rejoue la pose de repos.
        self.pub_angles = self.espion.create_publisher(
            Int32MultiArray, "/arm/servo_angles", 10)
        for noeud in (self.arbitre, self.base, self.entrees, self.espion):
            self.executeur.add_node(noeud)

        self.skills = ServeurSkills(registre=REGISTRE, demarrer=True)
        self.executif = MissionExecutive(registre=REGISTRE, journal_dir=journal_dir,
                                         demarrer=True)
        self.client_mission = ActionClient(self.espion, ExecuteMission,
                                           "/clawbot/execute_mission")
        self.client_decide = self.espion.create_client(SubmitDecision,
                                                       "/clawbot/mission/decide")
        self.client_report = self.espion.create_client(GetMissionReport,
                                                       "/clawbot/mission/report")

    def tourner(self, duree_s: float) -> None:
        fin = time.monotonic() + duree_s
        while time.monotonic() < fin:
            message = String()
            message.data = json.dumps({"capabilities": [
                {"name": "base", "state": "ACTIVE"}, {"name": "lidar", "state": "ACTIVE"},
                {"name": "wrist_vision", "state": "ACTIVE"}]})
            self.pub_capa.publish(message)
            angles = Int32MultiArray()
            angles.data = [90, 180, 0, 0, 90, 149]        # pose de repos validée (C10)
            self.pub_angles.publish(angles)
            image = Image()
            image.height, image.width, image.encoding = 4, 4, "rgb8"
            image.step = 12
            image.data = bytes([10, 20, 30] * 16)
            self.pub_image.publish(image)
            self.executeur.spin_once(timeout_sec=0.02)

    def envoyer(self, etapes, timeout_s_etape=0.0, objective="test"):
        goal = ExecuteMission.Goal()
        goal.mission_id = ""
        goal.objective = objective
        goal.steps_json = json.dumps([{"skill": s, "params": p, "timeout_s": timeout_s_etape}
                                      for s, p in etapes])
        futur = self.client_mission.send_goal_async(goal)
        self._attendre(futur, 30.0)
        return futur.result()

    def _attendre(self, futur, limite_s: float):
        fin = time.monotonic() + limite_s
        while not futur.done() and time.monotonic() < fin:
            self.tourner(0.05)
        assert futur.done(), "futur non résolu"

    def resultat(self, handle, limite_s=90.0):
        futur = handle.get_result_async()
        self._attendre(futur, limite_s)
        return futur.result().result

    def decider(self, mission_id, decision, params=None, rationale="test"):
        requete = SubmitDecision.Request()
        requete.mission_id = mission_id
        requete.decision = decision
        requete.params_json = json.dumps(params or {})
        requete.rationale = rationale
        futur = self.client_decide.call_async(requete)
        self._attendre(futur, 20.0)
        return futur.result()

    def rapport(self, mission_id=""):
        requete = GetMissionReport.Request()
        requete.mission_id = mission_id
        futur = self.client_report.call_async(requete)
        self._attendre(futur, 20.0)
        return json.loads(futur.result().report_json)


@pytest.fixture(scope="module")
def banc(tmp_path_factory):
    if not rclpy.ok():
        rclpy.init()
    banc = Banc(tmp_path_factory.mktemp("missions"))
    assert banc.client_mission.wait_for_server(timeout_sec=25.0), "exécutif injoignable"
    assert banc.client_decide.wait_for_service(timeout_sec=20.0)
    banc.tourner(2.0)
    yield banc
    banc.espion.destroy_publisher(banc.pub_angles)
    banc.executif.destroy_node()
    banc.skills.destroy_node()
    for noeud in (banc.arbitre, banc.base, banc.entrees, banc.espion):
        noeud.destroy_node()
    banc.executeur.shutdown()


def test_mission_sans_mouvement_reussit(banc):
    handle = banc.envoyer([("wait", {"seconds": 0.3}),
                           ("capture_image", {"camera": "wrist"})])
    assert handle.accepted
    resultat = banc.resultat(handle)
    assert resultat.state == "SUCCEEDED", resultat.summary_json
    resume = json.loads(resultat.summary_json)
    assert len(resume["steps"]) == 2
    journal = list((banc.executif.journal_dir).rglob("*.jsonl"))
    assert journal, "aucun journal écrit"
    lignes = [json.loads(l) for l in journal[0].read_text(encoding="utf-8").splitlines()]
    assert any(l["event"] == "SUCCEEDED" for l in lignes)


def test_echec_decision_puis_relance_aboutit(banc):
    """Chemin de reprise complet : échec → WAITING_DECISION → décision → SUCCEEDED.

    L'échec est déterministe (`wait` à 31 s : hors bornes, donc INVALID_PARAMS) pour
    ne pas dépendre de la convergence du simulateur ; la relance porte de nouveaux
    paramètres et doit rendre un **résultat de goal** — c'est le chemin sur lequel
    un LLM compte après un échec.
    """
    handle = banc.envoyer([("wait", {"seconds": 31})])
    assert handle.accepted

    fin = time.monotonic() + 60.0
    etat = ""
    while time.monotonic() < fin:
        banc.tourner(0.2)
        etat = banc.rapport().get("state", "")
        if etat == "WAITING_DECISION":
            break
    assert etat == "WAITING_DECISION", f"état {etat}"
    rapport = banc.rapport()
    assert rapport["failure_report"]["error_code"] == "INVALID_PARAMS"

    reponse = banc.decider(rapport["mission_id"], "RETRY_WITH_PARAMS",
                           {"seconds": 0.2}, rationale="délai dans les bornes")
    assert reponse.accepted, reponse.message
    assert reponse.escalations_left == 2

    resultat = banc.resultat(handle, limite_s=60.0)
    assert resultat.state == "SUCCEEDED", resultat.summary_json
    resume = json.loads(resultat.summary_json)
    assert resume["state"] == "SUCCEEDED"
    assert resume["decisions"][0]["decision"] == "RETRY_WITH_PARAMS"


def test_base_bloquee_mene_a_un_timeout_et_une_decision_attendue(banc):
    """Chaîne de sûreté : le skill échoue (TIMEOUT), la mission attend une décision."""
    banc.base.bloque = True
    handle = banc.envoyer([("move_relative", {"dx_m": 0.5})], timeout_s_etape=1.5)
    assert handle.accepted
    etat = ""
    fin = time.monotonic() + 60.0
    while time.monotonic() < fin:
        banc.tourner(0.2)
        etat = banc.rapport().get("state", "")
        if etat == "WAITING_DECISION":
            break
    assert etat == "WAITING_DECISION", f"état {etat}"
    assert banc.rapport()["failure_report"]["error_code"] == "TIMEOUT"
    banc.base.bloque = False
    banc.decider(banc.rapport()["mission_id"], "ABORT", rationale="fin du test")
    resultat = banc.resultat(handle, limite_s=60.0)
    assert resultat.state == "ABORTED", resultat.summary_json


def test_mission_refusee_si_une_autre_tourne(banc):
    """Une seule mission active : la seconde est refusée (REQ-EXEC-010, §5.2)."""
    handle = banc.envoyer([("wait", {"seconds": 1.0})])
    assert handle.accepted
    second = banc.client_mission.send_goal_async(_goal(["wait"], {"seconds": 0.2}))
    banc._attendre(second, 20.0)
    assert second.result().accepted is False
    resultat = banc.resultat(handle)
    assert resultat.state == "SUCCEEDED", resultat.summary_json


def _goal(skills, params):
    goal = ExecuteMission.Goal()
    goal.mission_id = ""
    goal.objective = "test"
    goal.steps_json = json.dumps([{"skill": s, "params": params} for s in skills])
    return goal
