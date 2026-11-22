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
MANIFESTE_REEL = Path(__file__).resolve().parents[1] / "config" / "expected_flows.yaml"

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


@pytest.mark.req("REQ-HEALTH-004")
def test_manifeste_reel_un_seul_abonnement_par_topic():
    """Aucun topic du manifeste réel n'est abonné deux fois (types incompatibles).

    Défaut constaté au premier démarrage du binaire : /voltage figurait dans le
    manifeste comme flux surveillé et recevait en plus un abonnement typé
    Float32 pour remplir `RobotHealth.voltage` ; DDS refuse deux abonnements de
    types différents sur le même topic et le nœud mourait dans son constructeur.
    """
    from rclpy.parameter import Parameter as P

    ctx = rclpy.Context()
    rclpy.init(context=ctx)
    node = MoniteurEspion(context=ctx, parameter_overrides=[
        P("flows_file", value=str(MANIFESTE_REEL)),
        P("assume_active_capabilities", value=["base", "lidar", "depth_vision"]),
    ])
    try:
        topics = [c[0] for c in node.captures]
        assert len(topics) == len(set(topics)), f"topic abonné deux fois : {sorted(topics)}"

        flux = {f.topic for f in node._flux}
        for topic, msg_type, qos, kwargs in node.captures:
            if topic in flux:
                brut = kwargs.get("raw") is True
                # exception documentée : /voltage porte une valeur lue dans RobotHealth
                if topic == "/voltage":
                    assert brut is False and msg_type.__name__ == "Float32"
                else:
                    assert brut is True, topic
                    assert qos.reliability == ReliabilityPolicy.BEST_EFFORT, topic
    finally:
        node.destroy_node()
        rclpy.shutdown(context=ctx)


@pytest.mark.req("REQ-HEALTH-004")
def test_abonnement_avec_le_type_reel_du_flux():
    """Chaque flux est abonné avec son type ROS réel, pas un type générique.

    Défaut constaté en production : les abonnements étaient tous déclarés `String`
    alors que `raw=True` ne dispense pas du bon type — DDS n'apparie que des types
    identiques, donc /scan (LaserScan), /odom (Odometry) et /cmd_vel_safe (Twist)
    ne recevaient jamais rien et étaient signalés périmés à tort.
    """
    from rclpy.parameter import Parameter as P

    ctx = rclpy.Context()
    rclpy.init(context=ctx)
    node = MoniteurEspion(context=ctx, parameter_overrides=[
        P("flows_file", value=str(MANIFESTE_REEL)),
        P("assume_active_capabilities", value=["base", "lidar", "depth_vision"]),
    ])
    try:
        attendus = {"/scan": "LaserScan", "/odom": "Odometry", "/cmd_vel_safe": "Twist",
                    "/imu/data_raw": "Imu", "/camera/depth/image_raw": "Image"}
        vus = {c[0]: c[1].__name__ for c in node.captures}
        for topic, classe in attendus.items():
            assert vus.get(topic) == classe, f"{topic} abonné en {vus.get(topic)}, attendu {classe}"
    finally:
        node.destroy_node()
        rclpy.shutdown(context=ctx)
