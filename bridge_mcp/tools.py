"""Catalogue des 22 outils MCP du pont (spécification §4.2 et §4.3).

Étape 4 : le contrat est satisfait — noms, schémas, annotations, enveloppes et refus typés.
Les outils qui exigent la couche ROS 2 ou l'arbitre refusent explicitement (`MCP-E-PREREQ`)
au lieu de renvoyer une valeur inventée.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server.mcpserver import MCPServer

from bridge_mcp import context, contract, limits
from bridge_mcp.envelope import error_result, not_wired, ok_result
from bridge_mcp.state import BridgeState

READ_ONLY = types.ToolAnnotations(read_only_hint=True)
DESTRUCTIVE = types.ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False)
IDEMPOTENT = types.ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True)

PROPOSALS_DIR = Path(os.environ.get("BRIDGE_PROPOSALS_DIR", "/tmp/clawbot-proposals"))


def _require_incident(state: BridgeState, incident_id: str | None):
    """Vérifie qu'une mutation vise un incident ouvert (MCP-10, MCP-12)."""
    if not incident_id:
        return None, error_result("MCP-E-ARG", "incident_id est obligatoire pour une mutation")
    incident = state.get(incident_id)
    if incident is None:
        return None, error_result("MCP-E-MODE", f"incident inconnu : {incident_id}")
    if incident.state != "open":
        return None, error_result("MCP-E-MODE", f"incident clos : {incident.state}")
    return incident, None


def _resources_snapshot() -> dict[str, Any]:
    """Ressources réelles du poste, lues dans /proc, sysfs et statvfs."""
    memory: dict[str, int] = {}
    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            key, _, rest = line.partition(":")
            if key in {"MemTotal", "MemAvailable"}:
                memory[key] = int(rest.split()[0]) // 1024
    load1, load5, load15 = os.getloadavg()
    stat = os.statvfs("/")
    thermal: dict[str, float] = {}
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        try:
            name = (zone / "type").read_text().strip()
            thermal[name] = int((zone / "temp").read_text().strip()) / 1000.0
        except OSError:
            continue
    return {
        "cpu_load_1m": round(load1, 2),
        "cpu_load_5m": round(load5, 2),
        "cpu_load_15m": round(load15, 2),
        "memory_total_mb": memory.get("MemTotal", 0),
        "memory_available_mb": memory.get("MemAvailable", 0),
        "disk_free_gb": round(stat.f_bavail * stat.f_frsize / 1e9, 2),
        "thermal_c": {name: round(value, 1) for name, value in thermal.items()},
        "voltage_v": None,
        "unavailable": ["voltage_v: aucune souscription ROS 2 dans cette version (ROS2-TOPIC-ABSENT)"],
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
    }


def register_tools(mcp: MCPServer, state: BridgeState) -> None:
    """Enregistre les 22 outils sur le serveur MCP."""

    # ── Lecture de contexte ────────────────────────────────────────────────
    @mcp.tool(name="incident_list", description="Liste les incidents connus du pont.", annotations=READ_ONLY)
    def incident_list(state_filter: str = "open", limit: int = 20) -> dict:
        items = [
            {k: v for k, v in incident.as_dict().items() if k != "trigger_snapshot"}
            for incident in state.incidents.values()
            if state_filter == "all" or incident.state == state_filter
        ]
        return ok_result({"incidents": items[: max(0, limit)], "total": len(items)})

    @mcp.tool(name="incident_get", description="Contexte complet d'un incident.", annotations=READ_ONLY)
    def incident_get(incident_id: str) -> Any:
        incident = state.get(incident_id)
        if incident is None:
            return error_result("MCP-E-ARG", f"incident inconnu : {incident_id}")
        if state.last_observation is None:
            return ok_result(
                {
                    **incident.as_dict(),
                    "context_unavailable": "CTX-01: aucune mesure disponible pour cet incident",
                }
            )
        return ok_result(
            {**incident.as_dict(), "context": context.build_context(incident, state.last_observation, state)}
        )

    @mcp.tool(name="graph_snapshot", description="Instantané du graphe ROS 2 : nœuds, topics, types, QoS.", annotations=READ_ONLY)
    def graph_snapshot(include_qos: bool = True) -> Any:
        return not_wired("graph_snapshot")

    @mcp.tool(name="tf_snapshot", description="Arêtes TF présentes, cadres manquants et péremption.", annotations=READ_ONLY)
    def tf_snapshot(root: str = "base_link", depth: int = 3) -> Any:
        return not_wired("tf_snapshot")

    @mcp.tool(name="topic_stats", description="Cadence, âge et nombre d'éditeurs d'un topic.", annotations=READ_ONLY)
    def topic_stats(topic: str, window_s: int = 5) -> Any:
        return not_wired("topic_stats")

    @mcp.tool(name="diagnostics", description="Dernier rapport de santé des périphériques, données indisponibles comprises.", annotations=READ_ONLY)
    def diagnostics(level: str = "all") -> Any:
        if state.last_health is None:
            return error_result("MCP-E-PREREQ", "aucun rapport de sante disponible : lancer bridge_mcp.health")
        return ok_result(state.last_health)

    @mcp.tool(name="param_get", description="Valeur, type et bornes d'un paramètre ROS 2.", annotations=READ_ONLY)
    def param_get(node: str, name: str) -> Any:
        return not_wired("param_get")

    @mcp.tool(name="param_list", description="Paramètres d'un nœud ROS 2 avec leur valeur courante.", annotations=READ_ONLY)
    def param_list(node: str) -> Any:
        return not_wired("param_list")

    @mcp.tool(name="logs_tail", description="Dernières entrées du journal du pont.", annotations=READ_ONLY)
    def logs_tail(since_iso: str = "", limit: int = 50) -> dict:
        entries = [
            entry
            for entry in state.audit
            if not since_iso or entry["at"] >= since_iso
        ]
        return ok_result({"entries": entries[-max(0, limit) :], "total": len(entries)})

    @mcp.tool(name="audit_tail", description="Dernières actions et décisions, avec identifiant de corrélation.", annotations=READ_ONLY)
    def audit_tail(incident_id: str = "", limit: int = 50) -> dict:
        entries = [
            entry
            for entry in state.audit
            if not incident_id or entry.get("incident_id") == incident_id
        ]
        return ok_result({"entries": entries[-max(0, limit) :], "total": len(entries)})

    @mcp.tool(name="resources_snapshot", description="Charge, mémoire, disque et températures du poste.", annotations=READ_ONLY)
    def resources_snapshot() -> dict:
        return ok_result(_resources_snapshot())

    @mcp.tool(name="capabilities", description="Outils autorisés, limites effectives et prérequis manquants.", annotations=READ_ONLY)
    def capabilities() -> dict:
        return ok_result(
            {
                "tools": list(contract.EXPECTED_TOOLS),
                "read_only_tools": list(contract.READ_ONLY_TOOLS),
                "mutation_tools": list(contract.MUTATION_TOOLS),
                "priority_tools": list(contract.PRIORITY_TOOLS),
                "limits": limits.LIMITS,
                "stop_latched": state.stop_latched,
                "error_codes": list(contract.ERROR_CODES),
            }
        )

    @mcp.tool(name="goal_list", description="Objectifs d'action actifs et actions disponibles.", annotations=READ_ONLY)
    def goal_list() -> Any:
        return not_wired("goal_list")

    # ── Intervention ──────────────────────────────────────────────────────
    @mcp.tool(name="param_set", description="Écrit un paramètre ROS 2 après contrôle de la liste blanche et des bornes.", annotations=DESTRUCTIVE)
    def param_set(
        incident_id: str | None = None,
        node: str = "",
        name: str = "",
        value: float | None = None,
        justification: str = "",
    ) -> Any:
        incident, refusal = _require_incident(state, incident_id)
        if refusal is not None:
            return refusal
        if name not in limits.LIMITS["allowed_params"]:
            return error_result("MCP-E-BOUNDS", f"paramètre hors liste blanche : {name}")
        bound = limits.LIMITS["max_angular_rs"] if name == "angular_limit" else limits.LIMITS["max_linear_ms"] * 10
        if value is None or abs(value) > bound:
            return error_result("MCP-E-BOUNDS", f"valeur hors bornes pour {name} : {value} (max {bound})")
        state.record("param_set", {"incident_id": incident_id, "node": node, "name": name, "value": value})
        return not_wired("param_set")

    @mcp.tool(name="param_restore", description="Rétablit la valeur d'un paramètre enregistrée avant l'incident.", annotations=IDEMPOTENT)
    def param_restore(incident_id: str | None = None, node: str = "", name: str = "") -> Any:
        _incident, refusal = _require_incident(state, incident_id)
        if refusal is not None:
            return refusal
        return not_wired("param_restore")

    @mcp.tool(name="goal_cancel", description="Annule un objectif d'action en cours.", annotations=IDEMPOTENT)
    def goal_cancel(incident_id: str | None = None, action: str = "", goal_id: str = "") -> Any:
        _incident, refusal = _require_incident(state, incident_id)
        if refusal is not None:
            return refusal
        return not_wired("goal_cancel")

    @mcp.tool(name="goal_send", description="Envoie un nouvel objectif d'action après vérification des prérequis.", annotations=DESTRUCTIVE)
    def goal_send(
        incident_id: str | None = None,
        action: str = "",
        goal: dict | None = None,
        justification: str = "",
    ) -> Any:
        _incident, refusal = _require_incident(state, incident_id)
        if refusal is not None:
            return refusal
        if action not in limits.LIMITS["allowed_actions"]:
            return error_result("MCP-E-PREREQ", f"action non déclarée : {action}")
        return not_wired("goal_send")

    @mcp.tool(name="safety_stop", description="Arrêt immédiat et verrou persistant, hors file des mutations.", annotations=IDEMPOTENT)
    def safety_stop(incident_id: str | None = None, reason: str = "") -> Any:
        if not reason:
            return error_result("MCP-E-ARG", "reason est obligatoire pour un arrêt")
        state.record("safety_stop_demande", {"incident_id": incident_id, "reason": reason})
        return error_result(
            "MCP-E-PREREQ",
            "arrêt non délivré : l'arbitre d'actionneurs n'est pas câblé ; utiliser l'arrêt physique",
        )

    @mcp.tool(name="spec_propose", description="Écrit une proposition de modification de spécification, sans exécution.", annotations=DESTRUCTIVE)
    def spec_propose(
        incident_id: str | None = None,
        exigence: str = "",
        changement: str = "",
        risques: str = "",
    ) -> Any:
        _incident, refusal = _require_incident(state, incident_id)
        if refusal is not None:
            return refusal
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        path = PROPOSALS_DIR / f"spec-{incident_id}.md"
        path.write_text(
            f"# Proposition de spécification\n\n- incident : {incident_id}\n- exigence : {exigence}\n"
            f"- changement : {changement}\n- risques : {risques}\n- produite le : {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n",
            encoding="utf-8",
        )
        state.record("spec_propose", {"incident_id": incident_id, "path": str(path)})
        return ok_result({"path": str(path), "applied": False})

    @mcp.tool(name="patch_propose", description="Écrit un correctif sur une branche dédiée, sans build ni déploiement.", annotations=DESTRUCTIVE)
    def patch_propose(
        incident_id: str | None = None,
        fichiers: list[str] | None = None,
        diff: str = "",
        tests_prevus: str = "",
    ) -> Any:
        _incident, refusal = _require_incident(state, incident_id)
        if refusal is not None:
            return refusal
        return not_wired("patch_propose")

    @mcp.tool(name="test_run", description="Exécute une suite de tests dans un environnement isolé.", annotations=DESTRUCTIVE)
    def test_run(suite: str = "contract", incident_id: str | None = None) -> Any:
        _incident, refusal = _require_incident(state, incident_id)
        if refusal is not None:
            return refusal
        return not_wired("test_run")

    @mcp.tool(name="escalate", description="Pose l'état escaladé, alerte l'opérateur et bloque les mutations.", annotations=IDEMPOTENT)
    def escalate(
        incident_id: str | None = None,
        motif: str = "",
        risque: str = "",
        action_demandee: str = "",
    ) -> Any:
        incident, refusal = _require_incident(state, incident_id)
        if refusal is not None:
            return refusal
        assert incident is not None
        incident.state = "escalated"
        state.record(
            "escalate",
            {"incident_id": incident_id, "motif": motif, "risque": risque, "action_demandee": action_demandee},
        )
        return ok_result(
            {
                "incident_id": incident_id,
                "state": incident.state,
                "channel": "audit",
                "delivered": False,
                "note": "canal opérateur non configuré (D-08)",
            }
        )


def register_resources(mcp: MCPServer, state: BridgeState) -> None:
    """Enregistre les ressources MCP statiques et le modèle d'incident (§4.5)."""

    @mcp.resource("spec://exigences")
    def exigences() -> str:
        return "\n".join(
            [
                "# Exigences du pont LLM2ROS",
                "",
                f"- outils : {len(contract.EXPECTED_TOOLS)}",
                f"- révision MCP : {contract.PROTOCOL_VERSION}",
                f"- codes d'erreur : {', '.join(contract.ERROR_CODES)}",
                f"- outils prioritaires : {', '.join(contract.PRIORITY_TOOLS)}",
            ]
        )

    @mcp.resource("robot://limites")
    def limites() -> str:
        return json.dumps(limits.LIMITS, ensure_ascii=False, indent=2)

    @mcp.resource("incident://{incident_id}")
    def incident(incident_id: str) -> str:
        found = state.get(incident_id)
        if found is None:
            return json.dumps({"status": "refused", "error": {"code": "MCP-E-ARG"}}, ensure_ascii=False)
        return json.dumps(found.as_dict(), ensure_ascii=False)
