"""Arrêt propre de l'arbitre (P02, REQ-OPS-011 et REQ-SAFETY-001)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from rclpy.executors import ExternalShutdownException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_safety import arbitrator  # noqa: E402


class _Journal:
    def __init__(self):
        self.avertissements = []

    def info(self, *_a, **_k):
        pass

    def warn(self, message, *_a, **_k):
        self.avertissements.append(str(message))


class _Editeur:
    def __init__(self):
        self.messages = []

    def publish(self, msg):
        self.messages.append(msg)


class _NoeudFactice:
    def __init__(self):
        self.pub_safe = _Editeur()
        self.journal = _Journal()
        self.etapes = []

    def get_logger(self):
        return self.journal

    def on_shutdown(self):
        # la vraie méthode est testée plus bas ; ici on enregistre l'appel
        self.etapes.append("on_shutdown")

    def destroy_node(self):
        self.etapes.append("destroy_node")


# ── REQ-OPS-011 : sortie 0 sur les deux signaux ──────────────────────────────

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

    monkeypatch.setattr(arbitrator.rclpy, "init", lambda *a, **k: None)
    monkeypatch.setattr(arbitrator.rclpy, "spin", spin_qui_arrete)
    monkeypatch.setattr(arbitrator.rclpy, "try_shutdown", lambda *a, **k: None)
    monkeypatch.setattr(arbitrator, "Arbitrator", lambda: factice)

    assert arbitrator.main() == 0
    assert factice.etapes == ["on_shutdown", "destroy_node"], (
        "l'arrêt doit publier les consignes nulles avant de détruire le nœud")


# ── REQ-SAFETY-001 : trois consignes nulles avant de quitter ─────────────────

@pytest.mark.req("REQ-SAFETY-001")
def test_on_shutdown_publie_trois_consignes_nulles():
    factice = _NoeudFactice()

    debut = time.monotonic()
    arbitrator.Arbitrator.on_shutdown(factice)
    duree = time.monotonic() - debut

    assert len(factice.pub_safe.messages) >= 3, (
        f"3 consignes nulles attendues, {len(factice.pub_safe.messages)} publiées")
    for msg in factice.pub_safe.messages[:3]:
        assert (msg.linear.x, msg.linear.y, msg.angular.z) == (0.0, 0.0, 0.0)
    # deux intervalles de 20 ms séparent trois publications
    assert duree >= 0.03, f"aucun intervalle entre les publications ({duree:.3f} s)"


@pytest.mark.req("REQ-SAFETY-001")
def test_on_shutdown_ne_propage_pas_une_erreur_de_publication():
    """Le contexte rclpy peut être déjà fermé : on journalise, on ne lève pas."""
    factice = _NoeudFactice()

    def publie_impossible(_msg):
        raise RuntimeError("context is invalid")

    factice.pub_safe.publish = publie_impossible

    arbitrator.Arbitrator.on_shutdown(factice)  # ne doit rien lever

    assert factice.journal.avertissements, "l'échec doit être journalisé"
