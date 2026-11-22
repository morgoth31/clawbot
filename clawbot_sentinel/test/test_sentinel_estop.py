"""La sentinelle déclenche l'e-stop au lieu de commander la vitesse (REQ-SAFETY-016)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_sentinel.sentinel_node import SentinelNode  # noqa: E402


class _Editeur:
    def __init__(self):
        self.messages = []

    def publish(self, msg):
        self.messages.append(msg)


class _Sentinelle(_Editeur):
    """Sentinelle sans ROS : seules les sorties qui nous intéressent existent."""


@pytest.mark.req("REQ-SAFETY-016")
def test_mot_arret_publie_estop_sans_twist():
    """Sur mot d'arrêt : Bool(True) sur /safety/estop, aucun Twist nulle part."""
    node = SentinelNode.__new__(SentinelNode)      # pas d'init ROS
    node.pub_cmd = _Editeur()                      # doit rester vide
    node.pub_estop = _Editeur()
    node.appeler_directeur = lambda *_a, **_k: None
    node.publier_evenement = lambda *_a, **_k: None

    node.arreter_localement("voix_arret")

    assert len(node.pub_estop.messages) == 1, "un seul e-stop par mot d'arrêt"
    msg = node.pub_estop.messages[0]
    assert msg.__class__.__name__ == "Bool" and msg.data is True
    assert node.pub_cmd.messages == [], "aucune consigne de vitesse ne doit partir"


@pytest.mark.req("REQ-SAFETY-016")
def test_aucune_publication_cmd_vel_dans_le_code():
    """Le nœud ne crée plus d'éditeur sur /cmd_vel*."""
    source = (Path(__file__).resolve().parents[1] / "clawbot_sentinel"
              / "sentinel_node.py").read_text(encoding="utf-8")
    for topic in ('"/cmd_vel"', '"/cmd_vel/teleop"', '"/cmd_vel/nav"', '"/cmd_vel/skill"'):
        assert f"create_publisher(Twist, {topic}" not in source, topic
