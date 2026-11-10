"""HLT-13 : `diagnostics` sert le dernier rapport de santé, sans le recalculer."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def _data(result) -> dict:
    """Le SDK enveloppe un succès sous `result` ; un refus typé garde `{status, error}`."""
    structured = result.structured_content or {}
    return structured.get("result", structured)["data"]


def test_diagnostics_returns_the_last_health_report(server, client):
    """HLT-13 : le rapport de santé est exposé tel quel, horodatage compris."""
    server.state.last_health = {
        "health_version": "1.0",
        "verdict": "degraded",
        "checked_at": "2026-11-10T08:26:00+08:00",
        "peripherals": [{"id": "PER-01", "name": "camera couleur", "verdict": "ok"}],
    }

    result = client.call_tool("diagnostics", {})
    data = _data(result)

    assert data["health_version"] == "1.0"
    assert data["verdict"] == "degraded"
    assert data["checked_at"]


def test_diagnostics_refuses_when_no_report_exists(server, client):
    """HLT-13 + HLT-18 : sans rapport, l'outil refuse avec un code, il n'invente pas."""
    result = client.call_tool("diagnostics", {})

    payload = result.structured_content or {}
    assert result.is_error is True
    assert payload["error"]["code"] == "MCP-E-PREREQ"
