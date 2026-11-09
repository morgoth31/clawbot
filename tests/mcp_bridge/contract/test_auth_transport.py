"""Tests de contrat — authentification et isolation du transport.

Exigences : MCP-03 (jeton), MCP-04 (boucle locale), SAF-04.
Rouges tant que le serveur n'est pas implémenté.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

from bridge_mcp import contract

pytestmark = pytest.mark.contract

INITIALIZE_REQUEST = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": contract.PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _post(url: str, token: str | None) -> httpx.Response:
    headers = dict(MCP_HEADERS)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.post(url, headers=headers, json=INITIALIZE_REQUEST, timeout=10.0)


def test_request_without_token_is_rejected(running, token):
    """MCP-03 : sans jeton, la requête est refusée (401) et rien n'est exécuté."""
    response = _post(running.url, token=None)
    assert response.status_code == 401


def test_request_with_wrong_token_is_rejected(running, token):
    """MCP-03 : un jeton erroné est refusé de la même manière qu'une absence de jeton."""
    response = _post(running.url, token="mauvais-jeton")
    assert response.status_code == 401
    assert response.json().get("detail", "") != "", "le refus doit être explicite"


def test_request_with_valid_token_is_accepted(running, token):
    """MCP-03 : le jeton attendu ouvre la session."""
    response = _post(running.url, token=token)
    assert response.status_code in (200, 202)


def test_listen_address_is_loopback_only(running):
    """MCP-04 : le port est lié à la boucle locale, jamais à toutes les interfaces."""
    host, port = running.bound_address
    assert host == "127.0.0.1"
    assert port != 0


@pytest.mark.skipif(
    os.environ.get("SKIP_LAN_CHECK") == "1", reason="contrôle réseau désactivé par l'exploitant"
)
def test_port_is_not_reachable_from_lan_address(running):
    """MCP-04 : la connexion depuis l'adresse LAN du robot doit échouer."""
    from support.harness import lan_address, port_is_reachable

    address = lan_address()
    if address is None:
        pytest.skip("aucune adresse LAN détectable sur ce poste")
    host, port = running.bound_address
    assert not port_is_reachable(address, port), f"le port {port} répond sur {address}"


def test_host_header_outside_allowlist_is_refused(running, token):
    """MCP-04 : protection contre le rebinding DNS (en-tête Host non déclaré)."""
    headers = dict(MCP_HEADERS)
    headers["Authorization"] = f"Bearer {token}"
    headers["Host"] = "attaquant.example"
    response = httpx.post(running.url, headers=headers, json=INITIALIZE_REQUEST, timeout=10.0)
    assert response.status_code in (400, 403, 421), (
        f"en-tête Host étranger accepté (code {response.status_code})"
    )


def test_error_body_never_leaks_the_expected_token(running):
    """SAF-04 : le refus ne divulgue pas le jeton attendu."""
    response = _post(running.url, token=None)
    body = json.dumps(response.json(), ensure_ascii=False)
    assert "test-" not in body
