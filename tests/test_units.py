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

# Les 14 unités du dépôt liées dans /etc/systemd/system et actives le 2026-11-22
# (systemctl list-units + ls -l /etc/systemd/system).
UNITES_ACTIVES = [
    "clawbot-director.service",
    "clawbot-docs.service",
    "clawbot-ekf.service",
    "clawbot-lidar.service",
    "clawbot-safety-arbitrator.service",
    "clawbot-sentinel.service",
    "clawbot-slam.service",
    "clawbot-wrist-camera.service",
    "orbbec-camera.service",
    "ros2-driver-node.service",
    "ros2-hardware-service.service",
    "ros2-llm-bridge-cpp.service",
    "rosbridge.service",
    "clawbot-yolo.service",
]

# Deux unités actives dont /etc porte encore une copie et non un lien : le
# dépôt doit tout de même les décrire (la bascule est une écriture dans /etc).
UNITES_HORS_LIEN = [
    "clawbot-description.service",
    "yahboom_oled.service",
]

UNITES_ROBOT = UNITES_ACTIVES + UNITES_HORS_LIEN


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
@pytest.mark.parametrize("nom", UNITES_ROBOT, ids=UNITES_ROBOT)
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


# ── REQ-OPS-012 ──────────────────────────────────────────────────────────────

@pytest.mark.req("REQ-OPS-012")
def test_documentation_ecoute_en_local():
    """mkdocs ne doit pas être joignable depuis le réseau."""
    cp = _lire("clawbot-docs.service")
    exec_start = cp.get("Service", "ExecStart")

    assert "127.0.0.1:8080" in exec_start, f"adresse locale absente : {exec_start!r}"
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


# ── C03 : dépendances et dossier d'état ──────────────────────────────────────

@pytest.mark.req("REQ-EXEC-020")
def test_l_executif_de_mission_ne_depend_pas_du_serveur_de_skills():
    """Un plantage du serveur de skills ne doit pas arrêter l'exécutif de mission."""
    cp = _lire("clawbot-mission-executive.service")
    for cle in ("Requires", "BindsTo", "PartOf"):
        valeur = cp.get("Unit", cle, fallback="")
        assert "clawbot-skill-server" not in valeur, (
            f"{cle}= cite le serveur de skills ({valeur}) : un arrêt du serveur "
            "arrêterait l'exécutif et rien ne le relancerait")
    assert "clawbot-skill-server" in cp.get("Unit", "Wants", fallback=""), (
        "Wants= doit conserver l'ordonnancement sans propager l'arrêt")
    assert "clawbot-skill-server" in cp.get("Unit", "After", fallback="")


@pytest.mark.req("REQ-EXEC-022")
@pytest.mark.parametrize("nom", [
    "clawbot-skill-server.service",
    "clawbot-mission-executive.service",
    "clawbot-yolo.service",
])
def test_les_unites_qui_ecrivent_dans_var_lib_declarent_leur_etat(nom):
    """StateDirectory crée le dossier ; ReadWritePaths le supposait déjà présent."""
    chemin = _chemin(nom)
    texte = chemin.read_text(encoding="utf-8")
    assert "/var/lib/clawbot" in texte, f"{nom} doit citer /var/lib/clawbot"
    cp = _lire(nom)
    assert cp.get("Service", "StateDirectory", fallback=None) == "clawbot", (
        f"{nom} : StateDirectory=clawbot attendu")
    chemins = cp.get("Service", "ReadWritePaths", fallback="").strip()
    assert chemins == "", (
        f"{nom} : ReadWritePaths={chemins} fait doublon avec StateDirectory et fait "
        "échouer le démarrage avant la création du dossier (226/NAMESPACE)")
