"""Fixtures communes aux tests du pont MCP.

Isolation (exigences ENV-01 à ENV-06 du plan de tests) :
- le domaine DDS de production (28) est interdit ;
- le serveur écoute sur un port éphémère en boucle locale ;
- aucune écriture hors `tmp_path` ;
- aucun processus externe (systemctl, launch) n'est démarré.

La session MCP vit dans un portail anyio dédié : le SDK ouvre des groupes de tâches, et les
faire traverser plusieurs boucles d'événements (fixtures asynchrones pytest) provoque
« Attempted to exit cancel scope in a different task ». Le portail garde la session et son
transport dans une seule boucle, ce qui rend les tests déterministes.
"""

from __future__ import annotations

import os
import secrets
from typing import Any, Iterator

import pytest
from mcp import ClientSession

from support.harness import ServerUnderTest
from support.session_worker import SessionWorker

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


class Client:
    """Façade synchrone sur le travailleur de session (voir `support/session_worker.py`)."""

    def __init__(self, worker) -> None:
        self._worker = worker
        self.init = worker.init

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        return self._worker.call_tool(name, arguments)

    def list_tools(self):
        return self._worker.list_tools()

    def list_resources(self):
        return self._worker.list_resources()

    def list_resource_templates(self):
        return self._worker.list_resource_templates()

    def read_resource(self, uri: str):
        return self._worker.read_resource(uri)


@pytest.fixture(scope="session", autouse=True)
def _environment_is_isolated() -> None:
    """Vérifie les variables d'isolation de la session (ENV-01, ENV-02)."""
    assert os.environ["ROS_DOMAIN_ID"] != PRODUCTION_DOMAIN
    assert os.environ["ROS_LOCALHOST_ONLY"] == "1"


@pytest.fixture
def token() -> str:
    """Jeton de test à usage unique, jamais le jeton réel (D-11)."""
    return f"test-{secrets.token_hex(16)}"


@pytest.fixture
def server(token: str):
    """Serveur construit par l'interface publique."""
    from bridge_mcp.server import create_server

    return create_server(token=token)


@pytest.fixture
def running(server) -> Iterator[ServerUnderTest]:
    """Serveur MCP servi sur un port éphémère en boucle locale."""
    from bridge_mcp.server import streamable_http_app

    app = streamable_http_app(server)
    with ServerUnderTest(app) as harness:
        yield harness


@pytest.fixture
def client(running: ServerUnderTest, token: str) -> Iterator[Client]:
    """Session MCP cliente authentifiée, initialisée une seule fois."""
    with SessionWorker(running.url, token) as worker:
        yield Client(worker)


@pytest.fixture
def connected(client: Client) -> Client:
    """Alias explicite : la session est déjà initialisée."""
    return client
