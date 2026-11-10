"""Le contexte du §6 doit être réellement transmis par `incident_get` (CTX-01, MCP-10)."""

from __future__ import annotations

import pytest

from support import observations

pytestmark = pytest.mark.contract


def _data(result):
    """Le SDK enveloppe `{status, data}` sous `result` dans `structured_content`."""
    structured = result.structured_content or {}
    return structured.get("result", structured)["data"]


def test_incident_get_returns_the_context_of_the_specification(server, client):
    """MCP-10 + CTX-01 : `incident_get` sert le contexte structuré, pas un résumé."""
    server.state.last_observation = observations.nominal()
    incident = server.state.open_incident(
        "TRG-03", 2, {"trigger": {"id": "TRG-03", "rule": "age > 3 periodes", "observed": {}, "threshold": {}}},
        subject="/voltage", allowed_tools=("context", "param_*", "escalate"),
    )

    result = client.call_tool("incident_get", {"incident_id": incident.incident_id})

    assert result.is_error is not True
    data = _data(result)
    context = data["context"]
    assert context["schema_version"] == "1.0"
    assert context["incident_id"] == incident.incident_id
    assert context["trigger"]["id"] == "TRG-03"
    assert context["policy"]["allowed_tools"] == ["context", "param_*", "escalate"]
    assert any("/scan" in entry for entry in context["unavailable"])


def test_incident_get_without_measurement_stays_honest(server, client):
    """CTX-01 : sans mesure disponible, le contexte n'est pas fabriqué."""
    incident = server.state.open_incident("TRG-05", 2, {}, subject="/voltage")

    result = client.call_tool("incident_get", {"incident_id": incident.incident_id})

    data = _data(result)
    assert "context" not in data, "aucun contexte ne doit être fabriqué sans mesure"
    assert "CTX-01" in data["context_unavailable"]
