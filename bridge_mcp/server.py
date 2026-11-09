"""Serveur MCP du pont LLM2ROS — construction et transport.

Étape 4 : le contrat est implémenté (catalogue, annotations, enveloppes, ressources,
authentification, isolation du transport). La couche ROS 2, le superviseur de déclencheurs
et l'arbitre d'actionneurs sont hors de cet incrément : les outils concernés refusent en
`MCP-E-PREREQ` plutôt que de renvoyer une valeur inventée.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from mcp.server.mcpserver import MCPServer

from bridge_mcp import contract, tools
from bridge_mcp.auth import McpGuardMiddleware
from bridge_mcp.state import BridgeState

VERSION = "0.1.0"

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


@dataclass
class BridgeServer:
    """Serveur MCP, état du pont et jeton d'authentification retenu."""

    mcp: MCPServer
    token: str
    state: BridgeState = field(default_factory=BridgeState)
    host: str = "127.0.0.1"
    port: int = 8090


def create_server(
    *,
    token: str,
    host: str = "127.0.0.1",
    port: int = 8090,
) -> BridgeServer:
    """Construit le serveur MCP authentifié du pont.

    Args:
        token: jeton porteur exigé sur chaque requête (exigence MCP-03).
        host: interface d'écoute, boucle locale uniquement (exigence MCP-04).
        port: port d'écoute ; 0 autorise un port éphémère pour les tests.

    Returns:
        Le serveur et son état, application HTTP non démarrée.

    Raises:
        ValueError: jeton vide, ou interface d'écoute hors boucle locale.
    """
    if not token:
        raise ValueError("un jeton non vide est obligatoire (MCP-03)")
    if host not in LOCAL_HOSTS:
        raise ValueError(f"écoute refusée hors boucle locale : {host} (MCP-04)")

    state = BridgeState()
    mcp = MCPServer(
        name=contract.SERVER_NAME,
        version=VERSION,
        description="Pont déterministe ROS 2 ↔ agent de raisonnement (Système 1 / Système 2).",
    )
    tools.register_tools(mcp, state)
    tools.register_resources(mcp, state)
    return BridgeServer(mcp=mcp, token=token, state=state, host=host, port=port)


def streamable_http_app(
    server: BridgeServer, *, allowed_hostnames: tuple[str, ...] | None = None
) -> Any:
    """Application ASGI servant le serveur MCP en HTTP streaming, protégée par jeton.

    L'authentification et la protection contre le rebinding DNS sont appliquées par
    `McpGuardMiddleware` sur le nom d'hôte, ce qui reste valable avec un port éphémère.
    """
    app = server.mcp.streamable_http_app(streamable_http_path="/mcp", host=server.host)
    return McpGuardMiddleware(
        app,
        token=server.token,
        allowed_hostnames=allowed_hostnames or LOCAL_HOSTS,
        protected_path="/mcp",
    )


def run(server: BridgeServer, *, port: int | None = None) -> None:
    """Démarre le serveur en HTTP streaming (appel bloquant)."""
    asyncio.run(server.mcp.run_streamable_http_async(
        host=server.host,
        port=server.port if port is None else port,
        streamable_http_path="/mcp",
    ))
