"""Un flux qui s'arrête devient périmé en moins de 3 s (REQ-HEALTH-001, O07).

Domaine 99 : le moniteur réel, un éditeur de test, et la mesure du délai entre
le dernier message et l'apparition du topic dans `stale_flows`.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

if os.environ.get("ROS_DOMAIN_ID") != "99":
    pytest.skip("test d'intégration : domaine 99 requis", allow_module_level=True)

RACINE = Path(__file__).resolve().parents[2]
for paquet in ("clawbot_health",):
    sys.path.insert(0, str(RACINE / paquet))

import rclpy  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from std_msgs.msg import String  # noqa: E402

from clawbot_interfaces.msg import RobotHealth  # noqa: E402

from clawbot_health.health_monitor import HealthMonitor  # noqa: E402

pytestmark = [pytest.mark.integration, pytest.mark.req("REQ-HEALTH-001")]

MANIFESTE = """flows:
  - {topic: /test_flux, min_hz: 5.0, max_age_s: 1.0, capability: base, critical: false}
"""


@pytest.fixture
def banc(tmp_path):
    manifeste = tmp_path / "expected_flows.yaml"
    manifeste.write_text(MANIFESTE, encoding="utf-8")

    ctx = rclpy.Context()
    rclpy.init(context=ctx)
    moniteur = HealthMonitor(context=ctx, parameter_overrides=[
        Parameter("flows_file", value=str(manifeste)),
        Parameter("assume_active_capabilities", value=["base"]),
    ])
    sonde = Node("sonde_sante", context=ctx)
    executeur = SingleThreadedExecutor(context=ctx)
    executeur.add_node(moniteur)
    executeur.add_node(sonde)
    threading.Thread(target=executeur.spin, daemon=True).start()

    etats = []
    sonde.create_subscription(RobotHealth, "/clawbot/health",
                              lambda m: etats.append((list(m.stale_flows), m.level)), 10)
    yield moniteur, sonde, etats

    executeur.shutdown()
    sonde.destroy_node()
    moniteur.destroy_node()
    rclpy.shutdown(context=ctx)


def attendre(predicat, limite_s, pas_s=0.05):
    fin = time.monotonic() + limite_s
    while time.monotonic() < fin:
        if predicat():
            return True
        time.sleep(pas_s)
    return False


def _stale(etats):
    """Dernier `stale_flows` publié, ou None si aucun état reçu."""
    return etats[-1][0] if etats else None


def test_flux_qui_s_arrete_devient_perime(banc):
    _moniteur, sonde, etats = banc
    editeur = sonde.create_publisher(String, "/test_flux", 1)

    # 2 s à 10 Hz : le flux est frais, il ne doit pas être signalé
    fin = time.monotonic() + 2.0
    while time.monotonic() < fin:
        editeur.publish(String(data="x"))
        time.sleep(0.1)
    assert attendre(lambda: _stale(etats) == [], 2.0), f"/test_flux signalé à tort : {etats[-2:]}"

    derniere = time.monotonic()
    assert attendre(lambda: "/test_flux" in (_stale(etats) or []), 3.0), \
        f"le flux doit apparaître dans stale_flows dans les 3 s : {etats[-2:]}"
    delai = time.monotonic() - derniere
    assert delai < 3.0, f"péremption détectée après {delai:.2f} s"
