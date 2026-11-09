"""Harnais de test : lance le serveur MCP sur un port éphémère, en boucle locale."""

from __future__ import annotations

import socket
import threading
import time
from typing import Any

import uvicorn


class ServerUnderTest:
    """Serveur MCP démarré en tâche de fond, joignable sur `http://127.0.0.1:<port>`."""

    def __init__(self, app: Any, host: str = "127.0.0.1") -> None:
        self._app = app
        self._host = host
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self.port: int | None = None

    @property
    def url(self) -> str:
        if self.port is None:
            raise RuntimeError("serveur non démarré")
        return f"http://{self._host}:{self.port}/mcp"

    @property
    def bound_address(self) -> tuple[str, int]:
        if self._server is None or self.port is None:
            raise RuntimeError("serveur non démarré")
        return self._host, self.port

    def __enter__(self) -> "ServerUnderTest":
        config = uvicorn.Config(self._app, host=self._host, port=0, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not self._server.started:
            time.sleep(0.02)
        if not self._server.started:
            raise RuntimeError("le serveur MCP n'a pas démarré dans les 10 s")

        sockets = self._server.servers[0].sockets
        self.port = sockets[0].getsockname()[1]
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("le serveur MCP ne s'est pas arrêté")


def lan_address() -> str | None:
    """Adresse IPv4 non locale du poste, pour prouver que le port n'est pas joignable."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))  # adresse de documentation, aucun paquet émis
        address = probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()
    return None if address.startswith("127.") else address


def port_is_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    """Vrai si une connexion TCP aboutit."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0
