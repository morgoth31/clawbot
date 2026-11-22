"""Tests de la profondeur Astra (P11) — manifeste, unité, dépendances par caméra."""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
MANIFESTE = RACINE / "clawbot_capabilities" / "config" / "capabilities.yaml"
UNITE = RACINE / "services" / "orbbec-camera.service"
SKILLS = RACINE / "clawbot_executive" / "config" / "skills.yaml"


def _unite() -> configparser.ConfigParser:
    lecteur = configparser.ConfigParser(strict=False, interpolation=None)
    lecteur.read_string(UNITE.read_text(encoding="utf-8"))
    return lecteur


@pytest.mark.req("REQ-PERC-003")
def test_depth_vision_est_geree_par_le_gestionnaire():
    import yaml

    manifeste = yaml.safe_load(MANIFESTE.read_text(encoding="utf-8"))["capacites"]
    depth = manifeste["depth_vision"]
    assert depth["managed"] is True
    assert depth["units"] == ["orbbec-camera.service"]
    assert depth.get("always_on") is False
    assert depth["ready_when"] == [{"topic": "/camera/depth/image_raw", "min_hz": 10.0}]


@pytest.mark.req("REQ-PERC-003")
def test_hardware_service_ne_lance_plus_lastra():
    source = (RACINE / "clawbot_bringup" / "clawbot_bringup" / "hardware_service.py").read_text(encoding="utf-8")
    for motif in ("astra_camera", "astro_pro", "orbbec-camera.service"):
        assert motif not in source, f"hardware_service lance encore l'Astra ({motif})"


@pytest.mark.req("REQ-PERC-003")
def test_unite_astra_durcie_comme_en_p02():
    service = _unite()["Service"]
    assert service.get("user") == "jetson"
    assert service.get("nonewprivileges") == "yes"
    assert service.get("protectsystem") in ("full", "strict")
    assert service.get("privatetmp") == "yes"
    assert service.get("restrictrealtime") == "yes"
    assert "ROS_LOG_DIR" in service.get("environment", "")
    assert service.get("restart") == "on-failure"
    assert service.get("user") == "jetson"


@pytest.mark.req("REQ-PERC-005")
def test_capture_image_depend_de_la_camera_demandee():
    import yaml

    skills = yaml.safe_load(SKILLS.read_text(encoding="utf-8"))["skills"]
    capture = skills["capture_image"]
    assert capture.get("requires") == []
    par_camera = capture.get("requires_by_param", {}).get("camera", {})
    assert par_camera["wrist"] == ["wrist_vision"]
    assert par_camera["astra"] == ["depth_vision"]
