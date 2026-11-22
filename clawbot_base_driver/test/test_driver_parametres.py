"""Paramètres déclarés par le pilote (P03, REQ-DRV-003) et source unique (REQ-DRV-001)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "clawbot_base_driver"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from clawbot_base_driver import base_driver  # noqa: E402
from soutien_pilote import (FausseHorloge, FauxJournal, FauxRosmaster, arreter,  # noqa: E402
                            instancier)

CHEMIN_MCU = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"


@pytest.fixture
def pilote():
    faux = FauxRosmaster()
    node = instancier(base_driver, faux, FausseHorloge(), FauxJournal())
    yield node
    arreter(node)


# ── REQ-DRV-003 : port série nommé ───────────────────────────────────────────

@pytest.mark.req("REQ-DRV-003")
def test_parametres_declares(pilote):
    """device_path et cmd_timeout_s, plus les paramètres historiques du pilote."""
    node = pilote

    assert node.get_parameter("device_path").value == CHEMIN_MCU
    assert node.get_parameter("cmd_timeout_s").value == 0.3

    for nom in ("Prefix", "angular_limit", "car_type", "imu_link",
                "xlinear_limit", "ylinear_limit"):
        assert node.has_parameter(nom), f"paramètre {nom} non déclaré"
    # use_sim_time est déclaré par rclpy lui-même pour tout nœud
    assert node.has_parameter("use_sim_time")


# ── REQ-DRV-001 : source unique ──────────────────────────────────────────────

@pytest.mark.req("REQ-DRV-001")
def test_aucune_copie_du_pilote_dans_le_depot():
    """Plus de Mcnamu_driver_X3.py versionné : le paquet en est la seule source."""
    restes = [
        p for p in RACINE.rglob("Mcnamu_driver_X3.py")
        if not {".git", "build", "install", "log"} & set(p.parts)
    ]
    assert restes == [], f"copies résiduelles : {restes}"


@pytest.mark.req("REQ-DRV-001")
def test_unite_execute_le_paquet_maison():
    """L'unité lance driver_node depuis le paquet du dépôt, pas depuis le vendor."""
    unite = (RACINE / "services" / "ros2-driver-node.service").read_text(encoding="utf-8")
    assert "clawbot_base_driver" in unite, unite
    assert "ros2 run yahboomcar_bringup" not in unite, unite
