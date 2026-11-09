"""Serveur MCP du pont LLM2ROS — interface publique.

Étape 3 : seule la signature est figée, par les tests de contrat. Aucune logique n'est
implémentée ici (étape 4). Toute implémentation doit satisfaire `bridge_mcp.contract`.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer


def create_server(
    *,
    token: str,
    host: str = "127.0.0.1",
    port: int = 8090,
) -> MCPServer:
    """Construit le serveur MCP authentifié du pont.

    Args:
        token: jeton porteur exigé sur chaque requête (exigence MCP-03).
        host: interface d'écoute, boucle locale uniquement (exigence MCP-04).
        port: port d'écoute ; 0 autorise un port éphémère pour les tests.

    Returns:
        Le serveur MCP configuré, serveur HTTP non démarré.

    Raises:
        NotImplementedError: tant que l'étape 4 n'a pas livré l'implémentation.
    """
    raise NotImplementedError(
        "étape 4 : implémentation du serveur MCP (catalogue, authentification, contexte)"
    )


def streamable_http_app(server: MCPServer, *, allowed_hosts: list[str] | None = None) -> Any:
    """Retourne l'application ASGI servant le serveur en HTTP streaming (exigence D-02)."""
    raise NotImplementedError("étape 4 : application ASGI du transport streamable HTTP")
