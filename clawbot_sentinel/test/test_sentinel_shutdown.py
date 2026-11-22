"""Arrêt propre de la sentinelle (P02, REQ-OPS-011).

`systemctl stop` envoie SIGINT (KillSignal) ou SIGTERM (défaut). rclpy traduit
SIGINT en KeyboardInterrupt et SIGTERM en ExternalShutdownException : les deux
doivent mener à un code de sortie 0, sinon l'unité finit en `failed` (R05, S19).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from rclpy.executors import ExternalShutdownException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_sentinel import sentinel_node  # noqa: E402


class _Journal:
    def info(self, *_a, **_k):
        pass

    def warn(self, *_a, **_k):
        pass


class _NoeudFactice:
    def __init__(self):
        self.ferme = False

    def get_logger(self):
        return _Journal()

    def fermer(self):
        self.ferme = True

    def destroy_node(self):
        pass


@pytest.mark.req("REQ-OPS-011")
@pytest.mark.parametrize(
    "signal_",
    [KeyboardInterrupt, ExternalShutdownException],
    ids=["SIGINT", "SIGTERM"],
)
def test_main_sort_en_zero(monkeypatch, signal_):
    factice = _NoeudFactice()

    def spin_qui_arrete(_noeud):
        raise signal_()

    monkeypatch.setattr(sentinel_node.rclpy, "init", lambda *a, **k: None)
    monkeypatch.setattr(sentinel_node.rclpy, "spin", spin_qui_arrete)
    monkeypatch.setattr(sentinel_node.rclpy, "try_shutdown", lambda *a, **k: None)
    monkeypatch.setattr(sentinel_node, "SentinelNode", lambda: factice)

    assert sentinel_node.main() == 0
    assert factice.ferme, "la sentinelle doit fermer proprement avant de quitter"
