"""Un flux qui s'arrête devient périmé en moins de 3 s (REQ-HEALTH-001, O07).

Le moniteur testé est le **binaire C++ déployé**, pas une instance Python : le test
le lance en domaine 99 avec un manifeste de test, publie /test_flux à 10 Hz puis
s'arrête, et mesure le délai d'apparition dans `stale_flows`.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

if os.environ.get("ROS_DOMAIN_ID") != "99":
    pytest.skip("test d'intégration : domaine 99 requis", allow_module_level=True)

RACINE = Path(__file__).resolve().parents[2]
BINAIRE = RACINE / "install" / "clawbot_health" / "lib" / "clawbot_health" / "health_monitor"

import rclpy  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import String  # noqa: E402

from clawbot_interfaces.msg import RobotHealth  # noqa: E402

pytestmark = [pytest.mark.integration, pytest.mark.req("REQ-HEALTH-001")]

MANIFESTE = """flows:
  - {topic: /test_flux, type: std_msgs/msg/String, min_hz: 5.0, max_age_s: 1.0, capability: base, critical: false}
"""


@pytest.fixture
def banc(tmp_path):
    if not BINAIRE.is_file():
        pytest.skip(f"binaire C++ non construit : {BINAIRE}")
    manifeste = tmp_path / "expected_flows.yaml"
    manifeste.write_text(MANIFESTE, encoding="utf-8")

    moniteur = subprocess.Popen(
        [str(BINAIRE), "--ros-args",
         "-p", f"flows_file:={manifeste}",
         "-p", "assume_active_capabilities:=[base]"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    ctx = rclpy.Context()
    rclpy.init(context=ctx)
    sonde = Node("sonde_sante", context=ctx)
    executeur = SingleThreadedExecutor(context=ctx)
    executeur.add_node(sonde)
    threading.Thread(target=executeur.spin, daemon=True).start()

    etats = []
    sonde.create_subscription(RobotHealth, "/clawbot/health",
                              lambda m: etats.append((list(m.stale_flows), m.level)), 10)
    try:
        yield sonde, etats
    finally:
        moniteur.terminate()
        try:
            moniteur.wait(timeout=5)
        except subprocess.TimeoutExpired:
            moniteur.kill()
        executeur.shutdown()
        sonde.destroy_node()
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
    sonde, etats = banc
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
