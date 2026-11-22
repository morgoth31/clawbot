"""Forme des fichiers d'unité systemd du robot (P02).

REQ-OPS-010 : politique de redémarrage et d'arrêt normalisée.
REQ-OPS-012 : la documentation n'écoute que sur la boucle locale.
REQ-OPS-013 : aucune commande de masse (pkill, killall, pgrep -f).

Le test lit les fichiers du dépôt, jamais /etc : les unités de
/etc/systemd/system sont des liens vers `services/` ou `systemd/`.
"""
from __future__ import annotations

import configparser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Les unités du robot qui suivent la politique P02 (RestartSec=2, TimeoutStopSec=10).
# Exceptions assumées, chacune avec sa raison : `clawbot-skill-server` et
# `clawbot-capability-manager` (KillSignal=SIGINT, 3 s / 15 s pour laisser le nœud
# rendre la main), `clawbot-mission-executive` (3/15), `clawbot-move-group` (5/15,
# MoveIt), `clawbot-nav2` (10/30, Nav2), `clawbot-arm-controller`, `clawbot-joy-teleop`
# et `clawbot-lidar` (5 s avant relance, matériel).
UNITES_ACTIVES = [
    "clawbot-director.service",
    "clawbot-ekf.service",
    "clawbot-health-monitor.service",
    "clawbot-safety-arbitrator.service",
    "clawbot-sentinel.service",
    "clawbot-slam.service",
    "clawbot-wrist-camera.service",
    "clawbot-yolo.service",
    "orbbec-camera.service",
    "ros2-driver-node.service",
    "ros2-hardware-service.service",
    "ros2-llm-bridge-cpp.service",
]

# Unités à la demande ou hors cible : décrites dans le dépôt, politiques propres.
UNITES_A_LA_DEMANDE = [
    "clawbot-arm-controller.service",
    "clawbot-capability-manager.service",
    "clawbot-joy-teleop.service",
    "clawbot-mission-executive.service",
    "clawbot-move-group.service",
    "clawbot-nav2.service",
    "clawbot-skill-server.service",
    "clawbot-lidar.service",
]

# Deux unités actives dont /etc porte encore une copie et non un lien : le dépôt doit tout
# de même les décrire (la bascule est une écriture dans /etc).
UNITES_HORS_LIEN = [
    "clawbot-description.service",
    "yahboom_oled.service",
]

# Unités à la demande et hors lien, vérifiées avec les autres.
UNITES_ROBOT = UNITES_ACTIVES + UNITES_HORS_LIEN + UNITES_A_LA_DEMANDE

# Les unités soumises à la politique standard (REQ-OPS-010). Les exceptions de
# UNITES_A_LA_DEMANDE ont leurs propres valeurs, vérifiées juste après.
UNITES_POLITIQUE = UNITES_ACTIVES + UNITES_HORS_LIEN

EXCEPTIONS = {
    "clawbot-arm-controller.service": ("5", "10"),
    "clawbot-capability-manager.service": ("3", "15"),
    "clawbot-joy-teleop.service": ("5", "10"),
    "clawbot-lidar.service": ("5", "10"),
    "clawbot-mission-executive.service": ("3", "15"),
    "clawbot-move-group.service": ("5", "15"),
    "clawbot-nav2.service": ("10", "30"),
    "clawbot-skill-server.service": ("3", "15"),
}


def _chemin(nom: str) -> Path:
    for dossier in ("services", "systemd"):
        candidat = REPO / dossier / nom
        if candidat.is_file():
            return candidat
    raise FileNotFoundError(f"{nom} introuvable dans services/ ou systemd/")


def _lire(nom: str) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    with _chemin(nom).open(encoding="utf-8") as flux:
        cp.read_file(flux)
    return cp


# ── REQ-OPS-010 ──────────────────────────────────────────────────────────────

@pytest.mark.req("REQ-OPS-010")
@pytest.mark.parametrize("nom", UNITES_POLITIQUE, ids=UNITES_POLITIQUE)
def test_politique_de_redemarrage_normalisee(nom):
    """Redémarrage sur panne avec délai, et arrêt borné."""
    cp = _lire(nom)
    assert cp.get("Unit", "StartLimitIntervalSec", fallback=None) == "60", (
        f"{nom} : StartLimitIntervalSec=60 attendu")
    assert cp.get("Unit", "StartLimitBurst", fallback=None) == "5", (
        f"{nom} : StartLimitBurst=5 attendu")
    assert cp.get("Service", "Restart", fallback=None) == "on-failure", (
        f"{nom} : Restart=on-failure attendu")
    assert cp.get("Service", "RestartSec", fallback=None) == "2", (
        f"{nom} : RestartSec=2 attendu")
    assert cp.get("Service", "TimeoutStopSec", fallback=None) == "10", (
        f"{nom} : TimeoutStopSec=10 attendu")


@pytest.mark.req("REQ-OPS-010")
@pytest.mark.parametrize("nom", sorted(EXCEPTIONS), ids=sorted(EXCEPTIONS))
def test_exceptions_de_politique_documentees(nom):
    """Une unité hors politique standard doit au moins porter les valeurs annoncées."""
    cp = _lire(nom)
    restart_sec, timeout = EXCEPTIONS[nom]
    assert cp.get("Service", "Restart", fallback=None) == "on-failure", nom
    assert cp.get("Unit", "StartLimitIntervalSec", fallback=None) == "60", nom
    assert cp.get("Unit", "StartLimitBurst", fallback=None) == "5", nom
    assert cp.get("Service", "RestartSec", fallback=None) == restart_sec, (
        f"{nom} : RestartSec={restart_sec} attendu, "
        f"lu {cp.get('Service', 'RestartSec', fallback=None)}")
    assert cp.get("Service", "TimeoutStopSec", fallback=None) == timeout, (
        f"{nom} : TimeoutStopSec={timeout} attendu, "
        f"lu {cp.get('Service', 'TimeoutStopSec', fallback=None)}")


# ── REQ-OPS-012 ──────────────────────────────────────────────────────────────

@pytest.mark.req("REQ-OPS-012")
def test_documentation_ecoute_en_local():
    """mkdocs ne doit pas être joignable depuis le réseau."""
    cp = _lire("clawbot-docs.service")
    exec_start = cp.get("Service", "ExecStart")

    # P14 (Q12) : `mkdocs build` puis service statique, lié à la boucle locale.
    assert "mkdocs build" in exec_start, f"construction absente : {exec_start!r}"
    assert "--bind 127.0.0.1" in exec_start, f"liaison locale absente : {exec_start!r}"
    assert "0.0.0.0" not in exec_start, f"écoute réseau encore présente : {exec_start!r}"


# ── REQ-OPS-013 ──────────────────────────────────────────────────────────────

FICHIERS_UNITE = sorted(
    [*(REPO / "services").glob("*.service"), *(REPO / "systemd").glob("*.service")]
)


@pytest.mark.req("REQ-OPS-013")
@pytest.mark.parametrize("fichier", FICHIERS_UNITE, ids=[f.name for f in FICHIERS_UNITE])
def test_aucune_commande_de_masse(fichier):
    """systemd est le seul contrôleur de processus autorisé."""
    texte = fichier.read_text(encoding="utf-8")
    for interdit in ("pkill", "killall", "pgrep -f"):
        assert interdit not in texte, f"{fichier.name} contient {interdit!r}"
