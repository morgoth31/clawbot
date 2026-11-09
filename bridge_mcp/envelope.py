"""Enveloppe de réponse des outils MCP (exigence MCP-11) et fabrique de résultats d'erreur."""

from __future__ import annotations

from typing import Any

import mcp.types as types

from bridge_mcp import contract


def status_ok(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Réponse de succès : `{status, data}`."""
    return {"status": "ok", "data": data or {}}


def status_refused(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """Refus explicite : `{status, error{code, message}}` (exigence MCP-13)."""
    if code not in contract.ERROR_CODES:
        raise ValueError(f"code d'erreur hors taxonomie : {code}")
    error: dict[str, Any] = {"code": code, "message": message}
    error.update(extra)
    return {"status": "refused", "error": error}


def error_result(code: str, message: str, **extra: Any) -> types.CallToolResult:
    """Résultat d'outil marqué en erreur, porteur d'un code stable.

    Un outil ne lève jamais d'exception : il retourne cette enveloppe, afin que le client
    reçoive un code exploitable plutôt qu'un message d'erreur générique du SDK.
    """
    payload = status_refused(code, message, **extra)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=f"{code}: {message}")],
        structured_content=payload,
        is_error=True,
    )


def ok_result(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Succès structuré : le SDK sérialise le dictionnaire en contenu JSON."""
    return status_ok(data)


def not_wired(feature: str) -> types.CallToolResult:
    """Refus typé pour une capacité dont la couche basse n'est pas encore câblée."""
    return error_result(
        "MCP-E-PREREQ",
        f"{feature} : couche non câblée dans cette version du pont",
        prerequis=["adaptateur ROS 2", "arbitre d'actionneurs"],
    )
