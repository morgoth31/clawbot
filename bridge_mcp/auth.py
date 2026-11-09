"""Authentification et isolation du transport MCP (exigences MCP-03, MCP-04, SAF-04).

L'application MCP est enveloppée par un intergiciel ASGI qui :
1. refuse toute requête sans jeton porteur valide, avec une comparaison à temps constant ;
2. refuse un en-tête `Host` hors liste blanche (protection contre le rebinding DNS) ;
3. ne laisse aucune trace du jeton attendu dans le corps de refus.
"""

from __future__ import annotations

import hmac
import json
from typing import Any, Awaitable, Callable

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]

SAFE_METHODS_WITHOUT_BODY = {"GET", "HEAD", "OPTIONS", "DELETE"}


class McpGuardMiddleware:
    """Jeton porteur + liste blanche d'en-têtes `Host` autour de l'application MCP."""

    def __init__(
        self,
        app: AsgiApp,
        *,
        token: str,
        allowed_hostnames: tuple[str, ...] = ("127.0.0.1", "localhost"),
        protected_path: str | None = None,
    ) -> None:
        if not token:
            raise ValueError("un jeton non vide est obligatoire (MCP-03)")
        self._app = app
        self._token = token.encode()
        self._allowed_hostnames = tuple(h.lower() for h in allowed_hostnames)
        self._protected_path = protected_path

    # ------------------------------------------------------------------ ASGI
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if self._protected_path is not None and path != self._protected_path:
            await self._app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}

        host = headers.get("host", "")
        hostname = host.rsplit(":", 1)[0].strip("[]").lower() if host else ""
        if hostname not in self._allowed_hostnames:
            await self._reject(send, 421, "En-tête Host refusé (rebinding DNS).")
            return

        provided = headers.get("authorization", "")
        scheme, _, value = provided.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(value.strip().encode(), self._token):
            await self._reject(send, 401, "Jeton porteur absent ou invalide.")
            return

        await self._app(scope, receive, send)

    # -------------------------------------------------------------- réponses
    @staticmethod
    async def _reject(send: Send, status: int, detail: str) -> None:
        body = json.dumps({"detail": detail}, ensure_ascii=False).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
