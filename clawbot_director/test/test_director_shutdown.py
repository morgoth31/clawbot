"""Arrêt propre du directeur (P02, REQ-OPS-011).

Le directeur ne rattrapait que KeyboardInterrupt : un SIGTERM (défaut systemd)
levait ExternalShutdownException et laissait l'unité en `failed`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from rclpy.executors import ExternalShutdownException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_director import director_node  # noqa: E402


class _Journal:
    def info(self, *_a, **_k):
        pass


class _NoeudFactice:
    def get_logger(self):
        return _Journal()

    def destroy_node(self):
        pass


@pytest.mark.req("REQ-OPS-011")
@pytest.mark.parametrize(
    "signal_",
    [KeyboardInterrupt, ExternalShutdownException],
    ids=["SIGINT", "SIGTERM"],
)
def test_main_sort_en_zero(monkeypatch, signal_):
    def spin_qui_arrete(_noeud):
        raise signal_()

    monkeypatch.setattr(director_node.rclpy, "init", lambda *a, **k: None)
    monkeypatch.setattr(director_node.rclpy, "spin", spin_qui_arrete)
    monkeypatch.setattr(director_node.rclpy, "try_shutdown", lambda *a, **k: None)
    monkeypatch.setattr(director_node, "DirectorNode", _NoeudFactice)

    assert director_node.main() == 0
