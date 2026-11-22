"""Intégration du multiplexeur et de l'e-stop en domaine 99 (P04).

Arbitre réel + `clawbot_sim/fake_inputs` + une sonde, dans un seul processus et
un exécuteur mono-thread : on vérifie ce qui sort vraiment sur `/cmd_vel_safe` et
`/safety/state`, pas seulement l'état interne du nœud.
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

# Les paquets maison sont importés depuis le dépôt, pas depuis install/ :
# on ajoute le dossier *parent* de chaque paquet (sinon le paquet régulier
# installé, prioritaire, masque la version en cours de développement).
RACINE = Path(__file__).resolve().parents[2]
for paquet in ("clawbot_safety", "clawbot_sim"):
    sys.path.insert(0, str(RACINE / paquet))

import rclpy  # noqa: E402
from geometry_msgs.msg import Twist  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy  # noqa: E402
from std_msgs.msg import Bool, String  # noqa: E402

from clawbot_safety.arbitrator import Arbitrator  # noqa: E402
from clawbot_sim.fake_inputs import FakeInputs  # noqa: E402

pytestmark = [pytest.mark.integration,
               pytest.mark.req("REQ-SAFETY-010"),
               pytest.mark.req("REQ-SAFETY-012")]


class Sonde(Node):
    def __init__(self, context):
        super().__init__("p04_sonde", context=context)
        qos_entree = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
        self.pub_skill = self.create_publisher(Twist, "/cmd_vel/skill", qos_entree)
        self.pub_teleop = self.create_publisher(Twist, "/cmd_vel/teleop", qos_entree)
        # TRANSIENT_LOCAL comme l'abonné : un éditeur VOLATILE est ignoré par DDS
        qos_estop = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                               durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.pub_estop = self.create_publisher(Bool, "/safety/estop", qos_estop)
        self.etat = {}
        self.sortie = None
        self.create_subscription(String, "/safety/state", self._sur_etat, 10)
        self.create_subscription(Twist, "/cmd_vel_safe", self._sur_sortie, 10)

    def _sur_etat(self, msg):
        try:
            self.etat = json.loads(msg.data)
        except ValueError:
            self.etat = {"state": msg.data}

    def _sur_sortie(self, msg):
        self.sortie = (msg.linear.x, msg.linear.y, msg.angular.z)

    def consigne(self, editeur, vx):
        msg = Twist()
        msg.linear.x = vx
        editeur.publish(msg)


def attendre(predicat, limite_s=3.0, pas_s=0.02):
    fin = time.monotonic() + limite_s
    while time.monotonic() < fin:
        if predicat():
            return True
        time.sleep(pas_s)
    return False


@pytest.fixture
def banc():
    ctx = rclpy.Context()
    rclpy.init(context=ctx)
    arbitre = Arbitrator(context=ctx)
    sim = FakeInputs(context=ctx)
    sonde = Sonde(ctx)
    executeur = SingleThreadedExecutor(context=ctx)
    for noeud in (arbitre, sim, sonde):
        executeur.add_node(noeud)
    fil = threading.Thread(target=executeur.spin, daemon=True)
    fil.start()
    yield arbitre, sonde
    executeur.shutdown()
    fil.join(timeout=2.0)
    for noeud in (sonde, sim, arbitre):
        noeud.destroy_node()
    rclpy.shutdown(context=ctx)


def test_priorite_puis_estop(banc):
    """skill seul → source skill ; teleop → teleop ; e-stop → zéro sous 100 ms."""
    _arbitre, sonde = banc

    assert attendre(lambda: sonde.etat.get("state") == "OK"), "capteurs simulés non vus"
    assert attendre(lambda: sonde.sortie is not None), "aucune sortie de l'arbitre"

    # 1. skill seul
    fin = time.monotonic() + 0.6
    while time.monotonic() < fin:
        sonde.consigne(sonde.pub_skill, 0.20)
        time.sleep(0.05)
    assert attendre(lambda: sonde.etat.get("source") == "skill"), sonde.etat

    # 2. téléopération concurrente : elle gagne malgré sa consigne plus faible
    fin = time.monotonic() + 0.4
    while time.monotonic() < fin:
        sonde.consigne(sonde.pub_skill, 0.20)
        sonde.consigne(sonde.pub_teleop, 0.05)
        time.sleep(0.05)
    assert attendre(lambda: sonde.etat.get("source") == "teleop"), sonde.etat
    assert sonde.sortie == (0.05, 0.0, 0.0), sonde.sortie

    # 3. arrêt d'urgence : sortie nulle au tick suivant
    depart = time.monotonic()
    sonde.pub_estop.publish(Bool(data=True))
    assert attendre(lambda: sonde.sortie == (0.0, 0.0, 0.0), limite_s=0.5), sonde.sortie
    delai = time.monotonic() - depart
    assert delai < 0.1, f"sortie nulle après {delai*1000:.0f} ms (> 100 ms)"
    assert attendre(lambda: sonde.etat.get("estop_latched") is True), sonde.etat
    assert sonde.etat.get("state") == "ESTOP_LATCHED"
