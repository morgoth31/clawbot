"""HLT-04 à HLT-07, HLT-12, HLT-17 : forme du rapport, bornes, stabilité, codes de sortie."""

from __future__ import annotations

import json

import pytest

from bridge_mcp import health
from support.fake_system import FakeGraphView, healthy_robot, measurement

pytestmark = pytest.mark.contract

PROBE_KEYS = {"probe", "level", "status", "observed", "threshold", "measured_at", "error_code", "detail"}
PERIPHERAL_KEYS = {"id", "name", "required", "verdict", "identity", "probes"}
VERDICTS = {"ok", "degraded", "failed", "unavailable", "skipped"}


def _report(**kwargs) -> dict:
    device, graph = kwargs.pop("pair", healthy_robot())
    return health.HealthChecker(device_view=device, graph_view=graph, now=lambda: 1000.0).run(**kwargs)


def test_every_peripheral_carries_a_complete_probe_contract():
    """HLT-04 : chaque sonde porte mesure, seuil, horodatage et code éventuel."""
    report = _report()

    assert set(report) >= {"health_version", "checked_at", "duration_ms", "verdict", "peripherals", "unavailable"}
    assert report["health_version"] == "1.0"
    assert report["verdict"] in VERDICTS
    assert isinstance(report["duration_ms"], int)

    for peripheral in report["peripherals"]:
        assert PERIPHERAL_KEYS <= set(peripheral), peripheral["id"]
        assert peripheral["verdict"] in VERDICTS
        assert peripheral["probes"], f"{peripheral['id']}: aucune sonde"
        for probe in peripheral["probes"]:
            assert PROBE_KEYS == set(probe), f"{probe.get('probe')}: contrat incomplet"
            assert probe["status"] in VERDICTS
            assert isinstance(probe["observed"], dict)
            assert isinstance(probe["threshold"], dict)
            assert probe["measured_at"]


def test_peripherals_follow_inventory_order():
    """HLT-07 : l'ordre du rapport suit l'inventaire, pas l'ordre de découverte."""
    report = _report()
    assert [item["id"] for item in report["peripherals"]] == [p.id for p in health.INVENTORY]


def test_report_is_bounded_and_free_of_secrets():
    """HLT-07 + HLT-17 : rapport ≤ 64 Ko, sans jeton ni chemin de credentials."""
    report = _report()
    rendered = json.dumps(report, ensure_ascii=False)

    assert len(rendered.encode()) <= 64 * 1024
    lowered = rendered.lower()
    for forbidden in ("authorization", "bearer", "token", "password", "id_rsa", ".ssh/"):
        assert forbidden not in lowered


def test_two_runs_without_change_give_the_same_verdicts():
    """HLT-07 : la comparaison entre deux rapports porte sur des verdicts identiques."""
    device, graph = healthy_robot()
    first = health.HealthChecker(device_view=device, graph_view=graph, now=lambda: 1000.0).run()
    second = health.HealthChecker(device_view=device, graph_view=graph, now=lambda: 1000.0).run()

    def strip(report: dict) -> dict:
        return {key: value for key, value in report.items() if key not in {"checked_at", "duration_ms"}}

    def strip_probes(report: dict) -> dict:
        return {
            item["id"]: [
                {k: v for k, v in probe.items() if k != "measured_at"} for probe in item["probes"]
            ]
            for item in report["peripherals"]
        }

    assert strip(first)["verdict"] == strip(second)["verdict"]
    assert strip_probes(first) == strip_probes(second)


def test_measured_window_is_shared_between_topics():
    """HLT-05 : toutes les mesures sont prises dans une seule fenêtre bornée."""
    device, graph = healthy_robot()
    health.HealthChecker(device_view=device, graph_view=graph, now=lambda: 1000.0).run()

    assert len(graph.calls) == 1, "une seule fenêtre de mesure par exécution"
    topics, window = graph.calls[0]
    assert window <= 5.0
    assert "/camera/color/image_raw" in topics


def test_exit_codes_follow_the_verdict():
    """HLT-12 : 0 ok, 1 degraded, 2 failed, 3 erreur interne."""
    assert health.exit_code_for({"verdict": "ok"}) == 0
    assert health.exit_code_for({"verdict": "degraded"}) == 1
    assert health.exit_code_for({"verdict": "failed"}) == 2
    assert health.exit_code_for({"verdict": "unavailable"}) == 0


def test_cli_prints_json_and_returns_the_verdict_code(monkeypatch, capsys):
    """HLT-12 : `--json` écrit un rapport valide et sort avec le code du verdict."""
    device, graph = healthy_robot()
    graph.topics["/camera/color/image_raw"] = measurement(rate_hz=2.0, age_s=0.01)

    code = health.main(
        ["--json", "--no-notify"],
        device_view=device,
        graph_view=graph,
        now=lambda: 1000.0,
    )

    captured = capsys.readouterr().out
    report = json.loads(captured)
    assert code == 2
    assert report["verdict"] == "failed"


def test_service_mode_returns_zero_even_when_verdict_is_failed(capsys):
    """HLT-15 : en mode service, un verdict `failed` n'échec pas l'unité systemd."""
    device, graph = healthy_robot()
    graph.topics["/camera/color/image_raw"] = measurement(rate_hz=2.0, age_s=0.01)

    code = health.main(["--json", "--no-notify", "--service-mode"],
                       device_view=device, graph_view=graph, now=lambda: 1000.0)

    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "failed"
    assert code == 0, "le mode service sort 0 : le verdict est dans le rapport et le message"
