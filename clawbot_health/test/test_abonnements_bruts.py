"""Les flux surveillés sont abonnés en brut, BEST_EFFORT, profondeur 1 (REQ-HEALTH-004)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "clawbot_health"))

rclpy = pytest.importorskip("rclpy")
from rclpy.parameter import Parameter  # noqa: E402
from rclpy.qos import ReliabilityPolicy  # noqa: E402

from clawbot_health.health_monitor import HealthMonitor  # noqa: E402

MANIFESTE = Path(__file__).resolve().parent / "manifeste_test.yaml"

pytestmark = pytest.mark.req("REQ-HEALTH-004")


class MoniteurEspion(HealthMonitor):
    """Capture les appels à create_subscription pour vérifier les arguments QoS."""

    def __init__(self, **kwargs):
        self.captures = []
        super().__init__(**kwargs)

    def create_subscription(self, msg_type, topic, callback, qos_profile, **kwargs):
        self.captures.append((topic, msg_type, qos_profile, kwargs))
        return super().create_subscription(msg_type, topic, callback, qos_profile, **kwargs)


@pytest.fixture
def moniteur():
    ctx = rclpy.Context()
    if not rclpy.ok(context=ctx):
        rclpy.init(context=ctx)
    node = MoniteurEspion(context=ctx, parameter_overrides=[
        Parameter("flows_file", value=str(MANIFESTE)),
        Parameter("assume_active_capabilities", value=["base"]),
    ])
    yield node
    node.destroy_node()
    rclpy.shutdown(context=ctx)


def test_chaque_flux_brut_en_best_effort(moniteur):
    flux = [c for c in moniteur.captures if c[0] == "/test_flux"]
    assert len(flux) == 1, f"/test_flux doit être abonné une fois : {moniteur.captures}"

    _topic, _type, qos, kwargs = flux[0]
    assert kwargs.get("raw") is True, "un flux surveillé ne se désérialise pas"
    assert qos.reliability == ReliabilityPolicy.BEST_EFFORT
    assert qos.depth == 1


def test_aucun_abonnement_deserialise_sur_un_flux(moniteur):
    """Tout abonnement à un topic du manifeste est brut : aucun type de message image."""
    topics_manifeste = {"/test_flux"}
    for topic, msg_type, _qos, kwargs in moniteur.captures:
        if topic in topics_manifeste:
            assert kwargs.get("raw") is True, topic
            assert msg_type.__name__ != "Image", topic
