"""Construction du contexte transmis à S2 (exigences CTX-01 à CTX-06).

Le contexte est un instantané borné : il ne contient que des mesures datées, et toute donnée
absente est déclarée avec un code (`ROS2-TOPIC-ABSENT`, `TF-FRAME-MISSING`, `ENOENT`). Aucun
secret, aucun chemin de credentials, aucune valeur inventée.
"""

from __future__ import annotations

import json
import os
import platform
import socket
import time
from typing import Any

from bridge_mcp import limits
from bridge_mcp.observations import Observation
from bridge_mcp.state import BridgeState, Incident

SCHEMA_VERSION = "1.0"
MAX_TOPICS = 200
MAX_LOGS = 200
MAX_COMMANDS = 50
MAX_BYTES = 256 * 1024

#: Absences structurelles constatées sur ce robot (contraintes C-01 à C-03).
STRUCTURAL_ABSENCES: tuple[tuple[str, str], ...] = (
    ("/scan", "ROS2-TOPIC-ABSENT"),
    ("/odom", "ROS2-TOPIC-ABSENT"),
    ("base_link", "TF-FRAME-MISSING"),
    ("odom", "TF-FRAME-MISSING"),
    ("map", "TF-FRAME-MISSING"),
    ("etat de charge batterie", "ENOENT"),
)


def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(epoch))


def _iso_now() -> str:
    return _iso(time.time())


def build_context(incident: Incident, observation: Observation, state: BridgeState) -> dict[str, Any]:
    """Assemble le contexte d'un incident selon le schéma du §6.1.

    Args:
        incident: incident ouvert par le moteur de déclenchement.
        observation: dernière mesure du robot, utilisée pour les blocs `graph`, `tf`, `resources`.
        state: état du pont, pour le journal borné.

    Returns:
        Le contexte complet, sérialisable en JSON et borné à 256 Ko.
    """
    topics = [
        {
            "name": topic.name,
            "declared_period_s": topic.declared_period_s,
            "publishers": 1 if topic.rate_hz > 0 else 0,
            "subscribers": 1,
            "rate_hz": topic.rate_hz,
            "nominal_rate_hz": topic.nominal_rate_hz,
            "last_age_s": round(topic.age_s, 3),
            "qos_incompatible": topic.qos_incompatible,
        }
        for topic in observation.topics[:MAX_TOPICS]
    ]

    trigger = dict(incident.payload.get("trigger", {}))
    trigger.setdefault("id", incident.trigger_id)
    trigger.setdefault("severity", incident.severity)
    trigger.setdefault("subject", incident.subject)
    trigger["occurrences"] = incident.occurrences

    unavailable = [f"{name}: {code}" for name, code in STRUCTURAL_ABSENCES]
    if observation.resources.voltage_v is None:
        unavailable.append("/voltage: ROS2-TOPIC-ABSENT")

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "incident_id": incident.incident_id,
        "created_at": _iso(incident.created_at),
        "read_at": _iso_now(),
        "trigger": trigger,
        "robot": {
            "host": socket.gethostname(),
            "ros_distro": os.environ.get("ROS_DISTRO", "inconnu"),
            "ros_domain_id": os.environ.get("ROS_DOMAIN_ID", "inconnu"),
            "bridge_version": "0.1.0",
            "mode": "surveillance",
            "uptime_s": _uptime_s(),
            "kernel": platform.release(),
        },
        "graph": {
            "nodes": [{"name": node.name, "alive": node.alive} for node in observation.nodes],
            "topics": topics,
            "actions": [{"name": action.name, "available": action.available} for action in observation.actions],
            "services": [
                {"name": service.name, "available": service.available} for service in observation.services
            ],
            "topics_omitted": max(0, len(observation.topics) - MAX_TOPICS),
        },
        "tf": {
            "frames_present": sorted(observation.tf_ages),
            "frames_expected_missing": [
                frame for frame in ("base_link", "odom", "map") if frame not in observation.tf_ages
            ],
            "edges": [
                {"frame": frame, "age_s": round(age, 3)} for frame, age in sorted(observation.tf_ages.items())
            ],
            "stale": any(age > 1.0 for age in observation.tf_ages.values()),
        },
        "diagnostics": {
            "items": [],
            "unavailable": ["/diagnostics: aucun éditeur déclaré dans cette version"],
        },
        "params": [],
        "resources": {
            "voltage_v": observation.resources.voltage_v,
            "disk_free_gb": observation.resources.disk_free_gb,
            "memory_available_mb": observation.resources.memory_available_mb,
            "thermal_c": dict(sorted(observation.resources.thermal_c.items())),
            "captured_at": _iso(incident.created_at),
        },
        "limits": {
            **{key: limits.LIMITS[key] for key in (
                "max_linear_ms",
                "max_angular_rs",
                "motion_watchdog_s",
                "allowed_params",
                "allowed_actions",
            )},
            "provisional": {name: value for name, (value, _ref) in _provisional().items()},
        },
        "recent_commands": [],
        "logs_tail": [
            {key: entry[key] for key in ("at", "event") if key in entry}
            for entry in state.audit[-MAX_LOGS:]
        ][:MAX_COMMANDS],
        "unavailable": unavailable,
        "policy": {
            "s2_min_severity": limits.LIMITS["s2_min_severity"],
            "budget": limits.LIMITS["budget"],
            "allowed_tools": list(incident.allowed_tools),
        },
        "spec_refs": ["TRG-A1", "CTX-01", "CTX-02", f"{incident.trigger_id}"],
    }

    return _enforce_bounds(payload)


def _provisional() -> dict[str, tuple[float, str]]:
    from bridge_mcp.triggers import PROVISIONAL_THRESHOLDS

    return PROVISIONAL_THRESHOLDS


def _uptime_s() -> int:
    try:
        with open("/proc/uptime", encoding="utf-8") as handle:
            return int(float(handle.read().split()[0]))
    except OSError:
        return 0


def _enforce_bounds(payload: dict[str, Any]) -> dict[str, Any]:
    """CTX-04 : réduit le contexte jusqu'à tenir sous la borne, en le déclarant."""
    rendered = json.dumps(payload, ensure_ascii=False).encode()
    if len(rendered) <= MAX_BYTES:
        return payload

    payload["graph"]["topics"] = payload["graph"]["topics"][:50]
    payload["logs_tail"] = payload["logs_tail"][-20:]
    payload["unavailable"].append(f"contexte tronque: {len(rendered)} octets > {MAX_BYTES}")
    return payload
