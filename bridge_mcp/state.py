"""État en mémoire du pont : incidents et journal d'audit (étape 4, sans ROS).

Le magasin est volontairement minimal : il sert le contrat d'outils et sera alimenté par le
superviseur de déclencheurs à l'étape suivante. Aucune donnée n'est inventée : un incident
absent est un refus typé, pas une réponse vide.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Incident:
    incident_id: str
    trigger_id: str
    severity: int
    state: str
    created_at: float
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "trigger_id": self.trigger_id,
            "severity": self.severity,
            "state": self.state,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(self.created_at)),
            "context": self.payload,
        }


class BridgeState:
    """Incidents ouverts, journal d'audit et verrou d'arrêt."""

    def __init__(self) -> None:
        self.incidents: dict[str, Incident] = {}
        self.audit: list[dict[str, Any]] = []
        self.stop_latched: bool = False

    def open_incident(self, trigger_id: str, severity: int, payload: dict[str, Any]) -> Incident:
        incident = Incident(
            incident_id=uuid.uuid4().hex,
            trigger_id=trigger_id,
            severity=severity,
            state="open",
            created_at=time.time(),
            payload=payload,
        )
        self.incidents[incident.incident_id] = incident
        self.record("incident_open", {"incident_id": incident.incident_id, "trigger": trigger_id})
        return incident

    def get(self, incident_id: str) -> Incident | None:
        return self.incidents.get(incident_id)

    def record(self, event: str, details: dict[str, Any]) -> None:
        self.audit.append(
            {
                "at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
                "event": event,
                **details,
            }
        )

    def latch_stop(self, reason: str) -> None:
        self.stop_latched = True
        self.record("safety_stop", {"reason": reason, "latched": True})
