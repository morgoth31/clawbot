"""Tests de contrat — ressources MCP.

Exigences : spécification §4.5 (ressources), CTX-01 (bloc de limites).
"""

from __future__ import annotations

import pytest

from bridge_mcp import contract

pytestmark = pytest.mark.contract


def test_static_resources_are_declared(client):
    """§4.5 : `spec://exigences` et `robot://limites` sont listées."""
    resources = client.list_resources()
    uris = {str(resource.uri) for resource in resources.resources}
    assert set(contract.STATIC_RESOURCES) <= uris


def test_incident_resource_template_is_declared(client):
    """§4.5 : le modèle `incident://{incident_id}` est exposé comme ressource paramétrée."""
    templates = client.list_resource_templates()
    uris = {template.uri_template for template in templates.resource_templates}
    assert contract.INCIDENT_RESOURCE_TEMPLATE in uris


def test_limits_resource_documents_effective_bounds(client):
    """CTX-01 : la ressource des limites expose les bornes réellement appliquées."""
    result = client.read_resource("robot://limites")
    payload = "".join(
        item.text for item in result.contents if getattr(item, "text", None)
    )
    assert "max_linear_ms" in payload
    assert "motion_watchdog_s" in payload
    assert "allowed_params" in payload
