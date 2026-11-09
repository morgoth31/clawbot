"""Tests de contrat — initialisation de la session MCP.

Exigences : MCP-02 (capacités), MCP-05 (identité), D-15 (révision négociée).
Rouges tant que `bridge_mcp.server.create_server` n'est pas implémenté (étape 4).
"""

from __future__ import annotations

import pytest

from bridge_mcp import contract

pytestmark = pytest.mark.contract


def test_capabilities_tools_and_resources_without_prompts(client):
    """MCP-02 : `tools` et `resources` sont annoncés, aucun prompt n'est servi.

    Écart documenté (D-16) : le SDK `mcp` 2.3.0 déclare systématiquement la capacité
    `prompts`, même sans prompt enregistré. Le contrat porte donc sur ce qui est
    réellement servi : la liste des prompts doit être vide.
    """
    capabilities = client.init.capabilities
    assert capabilities.tools is not None
    assert capabilities.resources is not None
    assert getattr(capabilities, "logging", None) is None
    assert getattr(capabilities, "sampling", None) is None
    prompts = client._worker._call(lambda session: session.list_prompts())  # noqa: SLF001
    assert list(getattr(prompts, "prompts", [])) == [], "aucun prompt ne doit être servi"


def test_server_identity(client):
    """MCP-05 : nom et version du serveur exposés."""
    assert client.init.server_info.name == contract.SERVER_NAME
    assert client.init.server_info.version, "la version du serveur doit être non vide"


def test_protocol_version_is_the_validated_revision(client):
    """D-15 : la révision négociée est 2025-11-25 et reste figée par contrat."""
    assert client.init.protocol_version == contract.PROTOCOL_VERSION
