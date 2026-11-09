"""Session MCP cliente pilotée depuis un fil, dans une seule boucle et une seule tâche.

Le SDK ouvre des groupes de tâches anyio : si la session est créée dans une tâche et fermée
dans une autre, le SDK lève « Attempted to exit cancel scope in a different task ». Ce
travailleur garde donc toute la durée de vie de la session dans une tâche unique et exécute
les commandes reçues depuis les tests via une file thread-safe.
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from concurrent.futures import Future
from typing import Any, Callable

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client


class SessionWorker:
    """Session MCP persistante, accessible de façon synchrone."""

    def __init__(self, url: str, token: str, *, timeout: float = 30.0) -> None:
        self._url = url
        self._token = token
        self._timeout = timeout
        self._commands: "queue.Queue[Any]" = queue.Queue()
        self._thread = threading.Thread(target=self._run_thread, daemon=True, name="mcp-session")
        self._ready = threading.Event()
        self._failure: BaseException | None = None
        self.init = None

    # ------------------------------------------------------------------ cycle
    def __enter__(self) -> "SessionWorker":
        self._thread.start()
        if not self._ready.wait(timeout=self._timeout):
            raise TimeoutError("session MCP non initialisée dans le délai imparti")
        if self._failure is not None:
            raise RuntimeError(f"initialisation de la session MCP échouée : {self._failure}")
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._commands.put(None)
        self._thread.join(timeout=self._timeout)

    # -------------------------------------------------------------- exécution
    def _run_thread(self) -> None:
        try:
            asyncio.run(self._main())
        except BaseException as exc:  # noqa: BLE001 - remonté au test
            self._failure = exc
            self._ready.set()

    async def _main(self) -> None:
        async with create_mcp_http_client(
            headers={"Authorization": f"Bearer {self._token}"}
        ) as http_client:
            async with streamable_http_client(self._url, http_client=http_client) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    self.init = await session.initialize()
                    self._ready.set()
                    while True:
                        command = await asyncio.get_running_loop().run_in_executor(
                            None, self._commands.get
                        )
                        if command is None:
                            return
                        action, args, future = command
                        try:
                            future.set_result(await action(session, *args))
                        except BaseException as exc:  # noqa: BLE001
                            future.set_exception(exc)

    def _call(self, action: Callable[..., Any], *args: Any) -> Any:
        future: Future = Future()
        self._commands.put((action, args, future))
        return future.result(timeout=self._timeout)

    # ------------------------------------------------------------------- API
    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return self._call(lambda session, n, a: session.call_tool(n, a), name, arguments or {})

    def list_tools(self) -> Any:
        return self._call(lambda session: session.list_tools())

    def list_resources(self) -> Any:
        return self._call(lambda session: session.list_resources())

    def list_resource_templates(self) -> Any:
        return self._call(lambda session: session.list_resource_templates())

    def read_resource(self, uri: str) -> Any:
        return self._call(lambda session, u: session.read_resource(u), uri)
