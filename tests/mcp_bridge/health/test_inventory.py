"""HLT-01, HLT-02, HLT-08 : inventaire déclaré, identité matérielle, périphérique non installé."""

from __future__ import annotations

import pytest

from bridge_mcp import health
from support.fake_system import healthy_robot

pytestmark = pytest.mark.contract


def test_inventory_declares_nine_peripherals_with_stable_ids():
    """HLT-01 : l'inventaire porte les identifiants PER-01 à PER-09, dans l'ordre."""
    assert [p.id for p in health.INVENTORY] == [f"PER-{n:02d}" for n in range(1, 10)]


def test_every_peripheral_declares_its_identity_and_probe_levels():
    """HLT-01 + HLT-02 : identité matérielle explicite, niveaux de sonde non vides."""
    for peripheral in health.INVENTORY:
        assert peripheral.levels, f"{peripheral.id}: aucun niveau de sonde"
        assert set(peripheral.levels) <= {"device", "ros", "functional", "http"}
        has_identity = bool(peripheral.usb or peripheral.by_id or peripheral.devices
                            or peripheral.input_class or peripheral.expected_frames
                            or peripheral.http_url)
        assert has_identity or peripheral.not_installed or peripheral.topic, (
            f"{peripheral.id}: aucune identité ni sujet à observer"
        )


def test_identity_is_never_an_index():
    """HLT-02 : aucun périphérique n'est identifié par un index brut `/dev/videoN`."""
    for peripheral in health.INVENTORY:
        assert (peripheral.usb or peripheral.by_id or peripheral.input_class
                or peripheral.expected_frames or peripheral.not_installed
                or peripheral.topic or peripheral.http_url), (
            f"{peripheral.id}: identité uniquement indexée"
        )


def test_required_peripherals_are_the_declared_five_plus_tf():
    """D-20 : le statut est rapporté à l'humain ; `requis` ne déclenche aucune action locale."""
    required = {p.id for p in health.INVENTORY if p.required}
    assert required == {"PER-01", "PER-02", "PER-03", "PER-04", "PER-05", "PER-09"}
    assert health.ACTIONS_ON_FAILURE == ()


def test_lidar_is_declared_not_installed_not_missing():
    """HLT-08 : le lidar est absent par conception, pas en panne."""
    lidar = health.INVENTORY_BY_ID["PER-06"]
    assert lidar.not_installed is True
    assert lidar.required is False


def test_report_marks_lidar_unavailable(monkeypatch):
    """HLT-08 : l'absence structurelle donne `unavailable`, jamais `failed`."""
    device, graph = healthy_robot()
    checker = health.HealthChecker(device_view=device, graph_view=graph, now=lambda: 1000.0)
    report = checker.run()

    lidar = next(item for item in report["peripherals"] if item["id"] == "PER-06")
    assert lidar["verdict"] == "unavailable"
    assert "HLT-E-NOT-INSTALLED" in " ".join(report["unavailable"])
