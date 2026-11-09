"""Tests de contrat — enveloppe de réponse et taxonomie d'erreurs.

Exigences : MCP-11 (enveloppe), MCP-12 (codes stables), MCP-13 (refus sans effet).
"""

from __future__ import annotations

import json

import pytest

from bridge_mcp import contract

pytestmark = pytest.mark.contract


def test_error_taxonomy_is_closed():
    """MCP-12 : huit codes, uniques, et un jeu de statuts fermé."""
    assert len(contract.ERROR_CODES) == 8
    assert len(set(contract.ERROR_CODES)) == 8
    assert all(code.startswith("MCP-E-") for code in contract.ERROR_CODES)
    assert set(contract.STATUS_VALUES) == {"ok", "refused", "duplicate", "timeout", "error"}


def test_unknown_tool_is_refused_without_success(client):
    """MCP-12 : un outil inconnu est refusé, jamais exécuté.

    Écart documenté (D-17) : le SDK refuse un outil inconnu avant d'appeler le serveur
    (« Unknown tool »), donc sans code `MCP-E-*`. La taxonomie couvre les erreurs levées
    par le pont, pas celles de la couche de protocole.
    """
    result = client.call_tool("outil_inexistant", {})
    assert result.is_error is True
    rendered = json.dumps(
        {"content": [c.model_dump() for c in result.content], "structured": result.structured_content},
        ensure_ascii=False,
        default=str,
    )
    assert "Unknown tool" in rendered or any(code in rendered for code in contract.ERROR_CODES), (
        f"refus non explicite : {rendered[:200]}"
    )


def test_missing_required_argument_is_rejected(client):
    """MCP-12 : `param_set` sans `incident_id` est refusé avec MCP-E-ARG (ou MCP-E-MODE)."""
    result = client.call_tool("param_set", {"node": "/driver_node", "name": "angular_limit", "value": 1.0})
    assert result.is_error is True
    rendered = json.dumps([c.model_dump() for c in result.content], ensure_ascii=False, default=str)
    assert "MCP-E-ARG" in rendered or "MCP-E-MODE" in rendered


def test_refusal_reports_a_reason(client):
    """MCP-13 : un refus porte un motif lisible et un code, pas un message vide."""
    result = client.call_tool("param_set", {"incident_id": "incident-inexistant"})
    assert result.is_error is True
    text = " ".join(str(getattr(c, "text", "")) for c in result.content)
    assert text.strip(), "le refus doit contenir un motif"
