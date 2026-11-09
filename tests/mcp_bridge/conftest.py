"""Fixtures communes aux tests du pont MCP.

Isolation (exigences ENV-01 à ENV-06 du plan de tests) :
- le domaine DDS de production (28) est interdit ;
- le serveur écoute sur un port éphémère en boucle locale ;
- aucune écriture hors `tmp_path` par les fixtures ;
- aucun processus externe (systemctl, launch) n'est démarré.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from mcp import ClientSession
from mcp.types import InitializeResult
from mcp.client.streamable_http import streamable_http_client

from support.harness import ServerUnderTest

PRODUCTION_DOMAIN = "28"
TEST_DOMAIN = "99"


def pytest_configure(config: pytest.Config) -> None:
    """Refuse de démarrer la session si le domaine de production est actif (ENV-01)."""
    domain = os.environ.get("ROS_DOMAIN_ID")
    if domain == PRODUCTION_DOMAIN:
        pytest.exit(
            "ROS_DOMAIN_ID=28 interdit pendant les tests : pollution du graphe réel (ENV-01)",
            returncode=2,
        )
    os.environ.setdefault("ROS_DOMAIN_ID", TEST_DOMAIN)
    os.environ["ROS_LOCALHOST_ONLY"] = "1"


@pytest.fixture(scope="session", autouse=True)
def _environment_is_isolated() -> None:
    """Vérifie a posteriori les variables d'isolation de la session."""
    assert os.environ["ROS_DOMAIN_ID"] != PRODUCTION_DOMAIN
    assert os.environ["ROS_LOCALHOST_ONLY"] == "1"


@pytest.fixture
def token() -> str:
    """Jeton de test à usage unique, jamais le jeton réel (D-11)."""
    return f"test-{secrets.token_hex(16)}"


@pytest.fixture
def server(token: str):
    """Serveur MCP construit par l'interface publique (échec rouge tant qu'il n'existe pas)."""
    from bridge_mcp.server import create_server

    return create_server(token=token)


@pytest.fixture
def running(server, token: str) -> Iterator[ServerUnderTest]:
    from bridge_mcp.server import streamable_http_app

    app = streamable_http_app(server)
    with ServerUnderTest(app) as harness:
        yield harness


@dataclass
class Connected:
    """Session MCP initialisée et résultat de l'initialisation (une seule fois par test)."""

    session: ClientSession
    init: InitializeResult
    url: str


@pytest_asyncio.fixture
async def connected(running: ServerUnderTest) -> AsyncIterator[Connected]:
    """Session MCP cliente réelle sur le transport HTTP streaming, déjà initialisée."""
    async with streamable_http_client(running.url) as streams:
        read_stream, write_stream = streams[0], streams[1]
        async with ClientSession(read_stream, write_stream) as client:
            init = await client.initialize()
            yield Connected(session=client, init=init, url=running.url)


@pytest_asyncio.fixture
async def session(connected: Connected) -> ClientSession:
    """Raccourci pour les tests qui n'ont pas besoin du résultat d'initialisation."""
    return connected.session
