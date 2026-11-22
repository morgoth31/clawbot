"""Serveur MCP : nœud rclpy + SDK FastMCP, stdio ou HTTP avec jeton (REQ-MCP-007).

Un thread tient l'executor rclpy, la boucle du SDK tourne dans le thread principal.
Les appels ROS passent par des futures avec délai : jamais de
`spin_until_future_complete` depuis un autre thread que celui de l'executor.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import rclpy
from rclpy.node import Node

from . import outils
from .outils import DESCRIPTIONS, OUTILS

REGISTRE_PAR_DEFAUT = "/home/jetson/clawbot/install/clawbot_executive/share/clawbot_executive/config/skills.yaml"
JETON_VARIABLE = "CLAWBOT_MCP_TOKEN"
MEMOIRE_MISSIONS = 50


def jeton_attendu() -> str | None:
    """Jeton lu dans l'environnement ; jamais dans le dépôt ni dans une unité versionnée."""
    valeur = os.environ.get(JETON_VARIABLE)
    return valeur or None


def verifier_jeton(entetes: dict, attendu: str | None) -> bool:
    """Un en-tête Authorization: Bearer <jeton> conforme, sinon refus."""
    if not attendu:
        return False
    valeur = ""
    for cle, contenu in (entetes or {}).items():
        if str(cle).lower() == "authorization":
            valeur = str(contenu)
            break
    if not valeur.lower().startswith("bearer "):
        return False
    return valeur[7:].strip() == attendu


def configurer_transport(transport: str, host: str, port: int) -> dict:
    """Paramètres de transport effectifs ; HTTP exige un hôte explicite."""
    if transport == "stdio":
        return {"transport": "stdio"}
    if transport != "http":
        raise ValueError(f"transport inconnu : {transport}")
    if not host or host in ("0.0.0.0", "::"):
        raise ValueError("HTTP : une interface explicite est requise (pas 0.0.0.0)")
    if not 1 <= int(port) <= 65535:
        raise ValueError(f"port invalide : {port}")
    return {"transport": "http", "host": host, "port": int(port)}


class ClawbotMCP(Node):
    """Nœud rclpy : clients de services/actions et éditeur d'e-stop uniquement."""

    def __init__(self, registre: str | Path | None = None):
        super().__init__("clawbot_mcp_server")
        from clawbot_interfaces.srv import (GetMissionReport, ListCapabilities,
                                           SetCapability, SubmitDecision)
        from rclpy.action import ActionClient
        from clawbot_interfaces.action import ExecuteMission
        from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
        from std_msgs.msg import Bool, String

        self.clients = {
            "capacites_list": self.create_client(ListCapabilities, "/clawbot/capabilities/list"),
            "capacites_set": self.create_client(SetCapability, "/clawbot/capabilities/set"),
            "mission_report": self.create_client(GetMissionReport, "/clawbot/mission/report"),
            "mission_decide": self.create_client(SubmitDecision, "/clawbot/mission/decide"),
        }
        self.types = {"capacites_list": ListCapabilities, "capacites_set": SetCapability,
                      "mission_report": GetMissionReport, "mission_decide": SubmitDecision}
        # Seul éditeur du serveur : le verrou d'arrêt d'urgence (REQ-MCP-004).
        qos_estop = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                               durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.pub_estop = self.create_publisher(Bool, "/safety/estop", qos_estop)
        self.derniere_sante: dict = {}
        self.create_subscription(String, "/clawbot/health", self._sur_sante, 10)
        self.actions = {"mission": ActionClient(self, ExecuteMission, "/clawbot/execute_mission")}
        self.missions: dict[str, dict] = {}

        from clawbot_executive.registre import charger
        chemin = str(registre or REGISTRE_PAR_DEFAUT)
        self.registre = charger(chemin)
        self.get_logger().info(f"clawbot_mcp pret : {len(OUTILS)} outils")

    def _sur_sante(self, message) -> None:
        try:
            detail = json.loads(message.data) if message.data.startswith("{") else {}
        except ValueError:
            detail = {}
        self.derniere_sante = {"raw": message.data, **detail}


class Contexte:
    """Adapte le nœud aux fonctions d'outils (clients injectables pour les tests)."""

    def __init__(self, node: ClawbotMCP | None = None, registre: dict | None = None,
                 clients: dict | None = None, editeur=None, horloge=time.monotonic):
        self.node = node
        self.clients = clients if clients is not None else (node.clients if node else {})
        self.types = node.types if node else {}
        self.registre = registre or (node.registre if node else {})
        self.editeur = editeur if editeur is not None else (node.pub_estop if node else None)
        self.horloge = horloge
        self.missions: dict[str, dict] = {}

    # ── accès bas niveau ─────────────────────────────────────────────────────
    def client(self, nom: str):
        return self.clients.get(nom)

    def requete(self, nom: str):
        classe = self.types.get(nom)
        if classe is None:
            from clawbot_interfaces.srv import (GetMissionReport, ListCapabilities,
                                               SetCapability, SubmitDecision)

            classe = {"capacites_list": ListCapabilities, "capacites_set": SetCapability,
                      "mission_report": GetMissionReport,
                      "mission_decide": SubmitDecision}[nom]
        return classe.Request()

    def sante(self) -> dict:
        return dict(self.node.derniere_sante) if self.node else {}

    def publier_estop(self) -> bool:
        if self.editeur is None:
            return False
        from std_msgs.msg import Bool

        self.editeur.publish(Bool(data=True))
        return True

    # ── missions ─────────────────────────────────────────────────────────────
    def lancer_mission(self, objective: str, etapes: list[dict],
                       max_duration_s: float) -> dict:
        from clawbot_interfaces.action import ExecuteMission

        client = self.node.actions["mission"] if self.node else None
        if client is None or not client.wait_for_server(timeout_sec=2.0):
            return outils.erreur("TIMEOUT", "exécutif de mission injoignable")
        goal = ExecuteMission.Goal()
        goal.mission_id = ""
        goal.objective = objective
        goal.steps_json = json.dumps(etapes, ensure_ascii=False)
        goal.max_duration_s = float(max_duration_s or 0.0)
        futur = client.send_goal_async(goal)
        if not outils._attendre(futur, 1.0):         # REQ-MCP-003 : < 1 s
            return outils.erreur("TIMEOUT", "envoi du goal sans réponse")
        handle = futur.result()
        if not handle.accepted:
            return outils.erreur("CAPABILITY_CONFLICT", "une mission est déjà en cours")
        mission_id = str(handle.goal_id.uuid)
        self.missions[mission_id] = {"mission_id": mission_id, "state": "RUNNING",
                                     "step_index": 0, "step_count": len(etapes),
                                     "progress": 0.0, "error_code": ""}
        handle.get_result_async().add_done_callback(
            lambda f, mid=mission_id: self._mission_finie(mid, f))
        return outils.ok(mission_id=mission_id)

    def _mission_finie(self, mission_id: str, futur) -> None:
        try:
            resultat = futur.result().result
            self.missions[mission_id].update({"state": resultat.state,
                                              "error_code": resultat.error_code})
        except Exception:                            # noqa: BLE001
            self.missions[mission_id].update({"state": "FAILED",
                                              "error_code": "UNHANDLED_EXCEPTION"})
        while len(self.missions) > MEMOIRE_MISSIONS:
            self.missions.pop(next(iter(self.missions)))

    def suivi(self, mission_id: str) -> dict | None:
        return self.missions.get(mission_id)

    def mission_en_cours(self) -> dict | None:
        for suivi in self.missions.values():
            if suivi.get("state") in ("RUNNING", "WAITING_DECISION", "PENDING"):
                return dict(suivi)
        return None

    def annuler(self, mission_id: str) -> bool:
        # L'annulation passe par l'exécutif (service de décision ABORT) : pas de shell.
        return self.missions.get(mission_id, {}).get("state") in (
            "RUNNING", "WAITING_DECISION") and self.missions[mission_id].update(
            {"state": "CANCELED"}) is None

    # ── image ────────────────────────────────────────────────────────────────
    def capture(self, camera: str) -> dict:
        return outils.erreur("CAPABILITY_INACTIVE",
                             f"capture_image indisponible pour {camera} "
                             "(capacité non ACTIVE)")


def _classe_serveur():
    """SDK MCP 2.x a renommé FastMCP en MCPServer ; on accepte les deux."""
    try:
        from mcp.server.mcpserver import MCPServer

        return MCPServer, "MCPServer"
    except ImportError:                            # pragma: no cover - mcp 1.x
        from mcp.server.fastmcp import FastMCP

        return FastMCP, "FastMCP"


def construire_serveur(ctx: Contexte):
    """Enregistre les douze outils avec leur signature explicite (schéma pour le LLM).

    Les paramètres sont déclarés un par un : c'est ce qui donne au client MCP un
    schéma utilisable. Un `*args, **kwargs` générique serait accepté par le SDK mais
    le LLM ne saurait pas quels champs envoyer.
    """
    classe, _variante = _classe_serveur()
    mcp = classe("clawbot_mcp")

    def emballer(nom: str, entree: dict) -> str:
        try:
            return json.dumps(OUTILS[nom](ctx, **entree), ensure_ascii=False)
        except Exception as exc:                     # noqa: BLE001 - REQ-MCP-005
            return json.dumps(outils.erreur("UNHANDLED_EXCEPTION", str(exc)[:300]),
                              ensure_ascii=False)

    @mcp.tool(name="get_robot_status", description=DESCRIPTIONS["get_robot_status"])
    def _get_robot_status() -> str:
        return emballer("get_robot_status", {})

    @mcp.tool(name="list_capabilities", description=DESCRIPTIONS["list_capabilities"])
    def _list_capabilities() -> str:
        return emballer("list_capabilities", {})

    @mcp.tool(name="set_capability", description=DESCRIPTIONS["set_capability"])
    def _set_capability(name: str, active: bool) -> str:
        return emballer("set_capability", {"name": name, "active": active})

    @mcp.tool(name="list_skills", description=DESCRIPTIONS["list_skills"])
    def _list_skills() -> str:
        return emballer("list_skills", {})

    @mcp.tool(name="start_skill", description=DESCRIPTIONS["start_skill"])
    def _start_skill(skill: str, params: dict | None = None,
                     timeout_s: float = 0.0) -> str:
        return emballer("start_skill", {"skill": skill, "params": params,
                                        "timeout_s": timeout_s})

    @mcp.tool(name="start_mission", description=DESCRIPTIONS["start_mission"])
    def _start_mission(objective: str, steps: list, max_duration_s: float = 0.0) -> str:
        return emballer("start_mission", {"objective": objective, "steps": steps,
                                          "max_duration_s": max_duration_s})

    @mcp.tool(name="get_mission_status", description=DESCRIPTIONS["get_mission_status"])
    def _get_mission_status(mission_id: str) -> str:
        return emballer("get_mission_status", {"mission_id": mission_id})

    @mcp.tool(name="cancel_mission", description=DESCRIPTIONS["cancel_mission"])
    def _cancel_mission(mission_id: str) -> str:
        return emballer("cancel_mission", {"mission_id": mission_id})

    @mcp.tool(name="get_failure_report", description=DESCRIPTIONS["get_failure_report"])
    def _get_failure_report(mission_id: str = "") -> str:
        return emballer("get_failure_report", {"mission_id": mission_id})

    @mcp.tool(name="submit_decision", description=DESCRIPTIONS["submit_decision"])
    def _submit_decision(mission_id: str, decision: str, rationale: str,
                         params: dict | None = None) -> str:
        return emballer("submit_decision", {"mission_id": mission_id,
                                            "decision": decision, "params": params,
                                            "rationale": rationale})

    @mcp.tool(name="stop_robot", description=DESCRIPTIONS["stop_robot"])
    def _stop_robot(reason: str = "") -> str:
        return emballer("stop_robot", {"reason": reason})

    @mcp.tool(name="get_snapshot", description=DESCRIPTIONS["get_snapshot"])
    def _get_snapshot(camera: str = "wrist") -> str:
        return emballer("get_snapshot", {"camera": camera})

    adaptateurs = {
        "get_robot_status": _get_robot_status, "list_capabilities": _list_capabilities,
        "set_capability": _set_capability, "list_skills": _list_skills,
        "start_skill": _start_skill, "start_mission": _start_mission,
        "get_mission_status": _get_mission_status, "cancel_mission": _cancel_mission,
        "get_failure_report": _get_failure_report, "submit_decision": _submit_decision,
        "stop_robot": _stop_robot, "get_snapshot": _get_snapshot,
    }
    return mcp, adaptateurs


def main(argv=None) -> int:
    import argparse

    parseur = argparse.ArgumentParser(description="Serveur MCP du Clawbot")
    parseur.add_argument("--transport", default="stdio", choices=("stdio", "http"))
    parseur.add_argument("--host", default="127.0.0.1")
    parseur.add_argument("--port", type=int, default=8765)
    arguments = parseur.parse_args(argv)

    transport = configurer_transport(arguments.transport, arguments.host, arguments.port)
    if transport["transport"] == "http" and not jeton_attendu():
        print(f"{JETON_VARIABLE} est requis pour le transport HTTP", flush=True)
        return 2

    rclpy.init()
    noeud = ClawbotMCP()
    executeur = rclpy.executors.SingleThreadedExecutor()
    executeur.add_node(noeud)
    fil = threading.Thread(target=executeur.spin, daemon=True)
    fil.start()
    mcp, _ = construire_serveur(Contexte(noeud))
    try:
        mcp.run(**transport)
    finally:
        executeur.shutdown(timeout_sec=2.0)
        noeud.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
