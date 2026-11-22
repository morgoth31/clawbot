"""Serveur d'action : rejet, préemption, annulation (REQ-EXEC-001, 005, 006)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

if os.environ.get("ROS_DOMAIN_ID") != "98":
    pytest.skip("tests rclpy : domaine 98 requis", allow_module_level=True)

RACINE = Path(__file__).resolve().parents[2]
REGISTRE = RACINE / "clawbot_executive" / "config" / "skills.yaml"

import rclpy  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.node import Node  # noqa: E402

from clawbot_interfaces.action import ExecuteSkill  # noqa: E402

pytestmark = [pytest.mark.req("REQ-EXEC-001"), pytest.mark.req("REQ-EXEC-005"),
              pytest.mark.req("REQ-EXEC-006")]


class PublieurFactice:
    """Capture ce que le serveur publie sur /cmd_vel/skill."""

    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


@pytest.fixture(scope="module")
def banc():
    from clawbot_executive.etats import Etats
    from clawbot_executive.serveur import ServeurSkills

    if not rclpy.ok():
        rclpy.init()
    etats = Etats()
    etats.capacites = {nom: {"name": nom, "state": "ACTIVE"}
                       for nom in ("base", "lidar", "wrist_vision", "navigation", "mapping")}
    etats.safety_state = "OK"
    etats.estop_latched = False
    publieur = PublieurFactice()
    serveur = ServeurSkills(registre=REGISTRE, etats=etats, editeur=publieur, demarrer=True)

    client_node = Node("client_skills_98")
    client = ActionClient(client_node, ExecuteSkill, "/clawbot/execute_skill")
    assert client.wait_for_server(timeout_sec=20.0), "serveur d'action injoignable"
    yield serveur, client, client_node, publieur

    serveur.destroy_node()
    client_node.destroy_node()


def envoyer(client, nom, params, timeout_s=0.0, attente_s=30.0):
    goal = ExecuteSkill.Goal()
    goal.mission_id = "test"
    goal.skill = nom
    goal.params_json = json.dumps(params)
    goal.timeout_s = timeout_s
    futur = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(client._node, futur, timeout_sec=attente_s)
    return futur.result()


def _resultat(noeud, handle, attente_s=30.0):
    futur = handle.get_result_async()
    rclpy.spin_until_future_complete(noeud, futur, timeout_sec=attente_s)
    assert futur.done(), "aucun résultat"
    return futur.result().result


def test_parametres_invalides_rejetes(banc):
    _, client, noeud, publieur = banc
    publieur.messages.clear()
    handle = envoyer(client, "move_relative", {"dx_m": 5.0})
    assert handle.accepted
    resultat = _resultat(noeud, handle)
    assert resultat.outcome == ExecuteSkill.Result.OUTCOME_REJECTED
    assert resultat.error_code == "INVALID_PARAMS"
    assert publieur.messages == [], "aucune consigne ne doit partir"
    rapport = json.loads(resultat.failure_report_json)
    assert rapport["skill"] == "move_relative", rapport["skill"]
    assert rapport["params"] == {"dx_m": 5.0}, rapport["params"]


def test_skill_inconnu_rejete(banc):
    _, client, noeud, _ = banc
    handle = envoyer(client, "teleport", {})
    assert handle.accepted
    resultat = _resultat(noeud, handle)
    assert resultat.outcome == ExecuteSkill.Result.OUTCOME_REJECTED
    assert resultat.error_code == "UNKNOWN_SKILL"


def test_wait_reussit(banc):
    _, client, noeud, _ = banc
    handle = envoyer(client, "wait", {"seconds": 0.3})
    assert handle.accepted
    resultat = _resultat(noeud, handle)
    assert resultat.outcome == ExecuteSkill.Result.OUTCOME_SUCCEEDED
    assert resultat.error_code == ""


def test_deuxieme_goal_rejete(banc):
    _, client, noeud, _ = banc
    long_handle = envoyer(client, "wait", {"seconds": 2.0})
    assert long_handle.accepted
    time.sleep(0.4)
    second = envoyer(client, "wait", {"seconds": 0.2})
    if second.accepted:
        resultat = _resultat(noeud, second)
        assert resultat.outcome == ExecuteSkill.Result.OUTCOME_REJECTED
    _resultat(noeud, long_handle)


def test_stop_preempte(banc):
    _, client, noeud, _ = banc
    long_handle = envoyer(client, "wait", {"seconds": 3.0})
    assert long_handle.accepted
    time.sleep(0.4)
    stop_handle = envoyer(client, "stop", {})
    assert stop_handle.accepted
    assert _resultat(noeud, stop_handle).outcome == ExecuteSkill.Result.OUTCOME_SUCCEEDED
    assert _resultat(noeud, long_handle).outcome in (
        ExecuteSkill.Result.OUTCOME_CANCELED, ExecuteSkill.Result.OUTCOME_FAILED)


def test_annulation_arrete_et_consigne_nulle(banc):
    _, client, noeud, publieur = banc
    handle = envoyer(client, "wait", {"seconds": 3.0})
    assert handle.accepted
    time.sleep(0.3)
    publieur.messages.clear()
    debut = time.monotonic()
    avenir = handle.cancel_goal_async()
    rclpy.spin_until_future_complete(noeud, avenir, timeout_sec=10.0)
    resultat = _resultat(noeud, handle)
    ecoule = time.monotonic() - debut
    assert resultat.outcome == ExecuteSkill.Result.OUTCOME_CANCELED
    assert ecoule < 0.2, f"annulation en {ecoule * 1000:.0f} ms"
    rclpy.spin_once(noeud, timeout_sec=0.2)
    assert publieur.messages and publieur.messages[-1].linear.x == 0.0
