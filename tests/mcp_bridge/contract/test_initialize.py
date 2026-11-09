"""Tests de contrat — initialisation de la session MCP.

Exigences : MCP-02 (capacités), MCP-05 (identité), D-15 (révision négociée).
Rouges tant que `bridge_mcp.server.create_server` n'est pas implémenté (étape 4).
"""

from __future__ import annotations

import pytest

from bridge_mcp import contract

pytestmark = pytest.mark.contract


async def test_capabilities_limited_to_tools_and_resources(connected):
    """MCP-02 : le serveur n'annonce que `tools` et `resources`."""
    capabilities = connected.init.capabilities
    assert capabilities.tools is not None
    assert capabilities.resources is not None
    assert capabilities.prompts is None
    assert getattr(capabilities, "logging", None) is None
    assert getattr(capabilities, "sampling", None) is None


async def test_server_identity(connected):
    """MCP-05 : nom et version du serveur exposés."""
    assert connected.init.server_info.name == contract.SERVER_NAME
    assert connected.init.server_info.version, "la version du serveur doit être non vide"


async def test_protocol_version_is_the_validated_revision(connected):
    """D-15 : la révision négociée est 2025-11-25 et reste figée par contrat."""
    assert connected.init.protocol_version == contract.PROTOCOL_VERSION
