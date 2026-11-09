"""Contrat d'interface du serveur MCP du pont LLM2ROS.

Ce module ne contient aucune logique : il fixe les données de spécification validées
(`llm2ros_mcp_specification.md`) que les tests de contrat vérifient et que l'implémentation
de l'étape 4 doit satisfaire. Toute modification ici est une modification de spécification.
"""

from __future__ import annotations

#: Révision négociée par le SDK `mcp` 2.3.0 (décision D-15, amendement de D-01).
PROTOCOL_VERSION = "2025-11-25"

#: Identité déclarée par le serveur (exigence MCP-05).
SERVER_NAME = "clawbot-bridge"

#: Outils de lecture de contexte (sûreté : aucune mutation).
READ_ONLY_TOOLS: tuple[str, ...] = (
    "incident_list",
    "incident_get",
    "graph_snapshot",
    "tf_snapshot",
    "topic_stats",
    "diagnostics",
    "param_get",
    "param_list",
    "logs_tail",
    "audit_tail",
    "resources_snapshot",
    "capabilities",
    "goal_list",
)

#: Outils de mutation ou d'écriture (sûreté : effet de bord, traçabilité obligatoire).
MUTATION_TOOLS: tuple[str, ...] = (
    "param_set",
    "param_restore",
    "goal_cancel",
    "goal_send",
    "safety_stop",
    "spec_propose",
    "patch_propose",
    "test_run",
    "escalate",
)

#: Les 22 outils attendus (exigences MCP-02, plan de tests §7.3).
EXPECTED_TOOLS: tuple[str, ...] = READ_ONLY_TOOLS + MUTATION_TOOLS

#: Outils prioritaires, hors file des mutations (exigence MCP-15).
PRIORITY_TOOLS: tuple[str, ...] = ("safety_stop", "escalate")

#: Outils autorisés en sévérité 4 (exigences SAF-05, TRG-23).
SEVERITY_4_TOOLS: tuple[str, ...] = ("safety_stop", "escalate")

#: Codes d'erreur stables (exigence MCP-12).
ERROR_CODES: tuple[str, ...] = (
    "MCP-E-AUTH",
    "MCP-E-ARG",
    "MCP-E-MODE",
    "MCP-E-BOUNDS",
    "MCP-E-PREREQ",
    "MCP-E-BUSY",
    "MCP-E-TIMEOUT",
    "MCP-E-INTERNAL",
)

#: Statuts d'enveloppe de réponse (exigence MCP-11).
STATUS_VALUES: tuple[str, ...] = ("ok", "refused", "duplicate", "timeout", "error")

#: Ressources MCP statiques (spécification §4.5).
STATIC_RESOURCES: tuple[str, ...] = ("spec://exigences", "robot://limites")

#: Modèle de ressource d'incident (§4.5).
INCIDENT_RESOURCE_TEMPLATE = "incident://{incident_id}"

#: Topics d'actionneurs qu'aucun outil ne doit publier (invariant SAF-01).
ACTUATOR_TOPICS: tuple[str, ...] = (
    "/cmd_vel",
    "/servo_ctrl",
    "/Buzzer",
    "/RGBLight",
)
