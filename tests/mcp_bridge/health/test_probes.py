"""HLT-02 à HLT-04, HLT-09, HLT-10, HLT-18 : comportement des sondes et agrégation."""

from __future__ import annotations

import dataclasses
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from bridge_mcp import health
from support.fake_system import FakeDeviceView, FakeGraphView, healthy_robot, measurement

pytestmark = pytest.mark.contract


def _check(device: FakeDeviceView, graph: FakeGraphView) -> dict:
    checker = health.HealthChecker(device_view=device, graph_view=graph, now=lambda: 1000.0)
    return checker.run()


def _peripheral(report: dict, identifier: str) -> dict:
    return next(item for item in report["peripherals"] if item["id"] == identifier)


def test_healthy_robot_is_ok():
    """Nominal : tous les périphériques requis conformes → verdict global `ok`."""
    device, graph = healthy_robot()
    report = _check(device, graph)

    assert report["verdict"] == "ok"
    assert _peripheral(report, "PER-01")["verdict"] == "ok"
    assert _peripheral(report, "PER-05")["verdict"] == "ok"


def test_moved_video_index_is_still_found():
    """HLT-02 : un index déplacé est retrouvé par l'identité USB, pas par le nom."""
    device, graph = healthy_robot()
    device.video = {"/dev/video5": "0c45:6340"}
    device.present = {"/dev/video5", "/dev/ttyUSB1", "/dev/myserial"}
    report = _check(device, graph)

    assert _peripheral(report, "PER-01")["verdict"] == "ok"
    assert _peripheral(report, "PER-01")["identity"]["device"] == "/dev/video5"


def test_foreign_device_on_the_expected_index_is_a_mismatch():
    """HLT-02 : un autre matériel au même emplacement est refusé explicitement."""
    device, graph = healthy_robot()
    device.video = {"/dev/video0": "1234:5678"}
    report = _check(device, graph)

    camera = _peripheral(report, "PER-01")
    assert camera["verdict"] == "failed"
    codes = {probe["error_code"] for probe in camera["probes"]}
    assert "HLT-E-IDENTITY-MISMATCH" in codes


def test_camera_device_present_but_topic_silent_keeps_levels_independent():
    """HLT-03 : le niveau `device` reste `ok` quand le niveau `ros` échoue."""
    device, graph = healthy_robot()
    graph.topics.pop("/camera/color/image_raw")
    report = _check(device, graph)

    camera = _peripheral(report, "PER-01")
    by_level = {probe["level"]: probe for probe in camera["probes"]}
    assert by_level["device"]["status"] == "ok"
    assert by_level["ros"]["status"] == "failed"
    assert by_level["ros"]["error_code"] == "HLT-E-TOPIC-SILENT"
    assert camera["verdict"] == "failed"


def test_rate_below_half_is_failed_and_between_half_and_eighty_is_degraded():
    """D-21 (provisoire) : 40 % → failed, 60 % → degraded, 90 % → ok."""
    device, graph = healthy_robot()

    graph.topics["/camera/color/image_raw"] = measurement(rate_hz=8.0, age_s=0.01)
    assert _peripheral(_check(device, graph), "PER-01")["verdict"] == "failed"

    graph.topics["/camera/color/image_raw"] = measurement(rate_hz=12.0, age_s=0.01)
    assert _peripheral(_check(device, graph), "PER-01")["verdict"] == "degraded"

    graph.topics["/camera/color/image_raw"] = measurement(rate_hz=18.0, age_s=0.01)
    assert _peripheral(_check(device, graph), "PER-01")["verdict"] == "ok"


def test_optional_peripheral_failure_does_not_degrade_global_verdict():
    """HLT-09 + HLT-10 : manette absente malgré un service actif → visible, verdict global inchangé."""
    device, graph = healthy_robot()
    device.inputs = {}  # aucun /dev/input/js0 : la manette est optionnelle
    report = _check(device, graph)

    joystick = _peripheral(report, "PER-07")
    assert joystick["verdict"] == "failed"
    assert report["verdict"] == "ok"
    assert "PER-07" in {item["id"] for item in report["peripherals"] if item["verdict"] == "failed"}


def test_missing_measurement_is_null_with_a_code_never_zero():
    """HLT-18 : une mesure impossible vaut `null` et porte un code, jamais 0."""
    device, graph = healthy_robot()
    graph.topics.pop("/voltage")
    report = _check(device, graph)

    battery = _peripheral(report, "PER-05")
    ros_probe = next(probe for probe in battery["probes"] if probe["level"] == "ros")
    assert ros_probe["observed"]["rate_hz"] is None
    assert ros_probe["error_code"] == "HLT-E-TOPIC-SILENT"
    assert battery["verdict"] == "failed"


def test_serial_device_held_by_two_processes_is_reported():
    """HLT-04 + HLT-06 : le port tenu par plusieurs processus est signalé, pas corrigé."""
    device, graph = healthy_robot()
    device.holders["/dev/ttyUSB1"] = [5976, 6120]
    report = _check(device, graph)

    mcu = _peripheral(report, "PER-04")
    codes = {probe["error_code"] for probe in mcu["probes"]}
    assert "HLT-E-USED-BY-OTHER" in codes


def test_tf_frames_expected_are_checked():
    """PER-09 : l'arbre TF est jugé sur les cadres attendus, absents aujourd'hui."""
    device, graph = healthy_robot()
    graph.tf_frames = {"camera_link", "camera_color_frame"}
    report = _check(device, graph)

    tf = _peripheral(report, "PER-09")
    assert tf["verdict"] == "failed"
    assert "HLT-E-NODE-ABSENT" in {probe["error_code"] for probe in tf["probes"]}


class _Endpoint(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self) -> None:  # noqa: N802
        body = b'{"status": "ok"}'
        self.send_response(type(self).status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        return


@pytest.fixture
def endpoint():
    _Endpoint.status = 200
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/health", _Endpoint
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _inventory_with_detection_endpoint(url: str):
    return tuple(
        dataclasses.replace(item, http_url=url) if item.id == "PER-08" else item
        for item in health.INVENTORY
    )


def test_detection_chain_is_probed_over_http(endpoint):
    """PER-08 : la chaîne de détection expose son état en HTTP, pas sur un topic ROS."""
    url, _handler = endpoint
    device, graph = healthy_robot()
    report = health.HealthChecker(
        device_view=device, graph_view=graph, now=lambda: 1000.0,
        inventory=_inventory_with_detection_endpoint(url),
    ).run()

    detection = _peripheral(report, "PER-08")
    assert detection["verdict"] == "ok"
    assert detection["probes"][0]["level"] == "http"


def test_http_endpoint_failure_is_reported(endpoint):
    """HLT-18 : un point d'entrée muet est déclaré, avec son code."""
    url, handler = endpoint
    handler.status = 503
    device, graph = healthy_robot()
    report = health.HealthChecker(
        device_view=device, graph_view=graph, now=lambda: 1000.0,
        inventory=_inventory_with_detection_endpoint(url),
    ).run()

    detection = _peripheral(report, "PER-08")
    assert detection["verdict"] == "failed"
    assert detection["probes"][0]["error_code"] == "HLT-E-UNAVAILABLE"
