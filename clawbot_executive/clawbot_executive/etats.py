"""État partagé lu par les skills : capacités, sûreté, odométrie.

Un skill ne crée pas ses propres abonnements (P08 §5.1) : le serveur tient cet
objet, les skills le lisent.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field


@dataclass
class Etats:
    capacites: dict[str, dict] = field(default_factory=dict)
    safety_state: str = "UNKNOWN"
    estop_latched: bool = False
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    odom_recue: bool = False

    # ── capacités ────────────────────────────────────────────────────────────
    def capacite_active(self, nom: str) -> bool:
        entree = self.capacites.get(nom) or {}
        return entree.get("state") in ("ACTIVE", "STARTING")

    def maj_capacites(self, charge: str) -> None:
        try:
            document = json.loads(charge)
        except (TypeError, ValueError):
            return
        for entree in document.get("capabilities", []):
            if entree.get("name"):
                self.capacites[entree["name"]] = entree

    # ── sûreté ───────────────────────────────────────────────────────────────
    def maj_safety(self, charge: str) -> None:
        try:
            document = json.loads(charge)
        except (TypeError, ValueError):
            return
        self.safety_state = str(document.get("state", "UNKNOWN"))
        self.estop_latched = bool(document.get("estop_latched", False))

    # ── odométrie ────────────────────────────────────────────────────────────
    def maj_odom(self, x: float, y: float, yaw: float) -> None:
        self.x, self.y, self.yaw = x, y, yaw
        self.odom_recue = True

    @staticmethod
    def lacet(quaternion) -> float:
        x, y, z, w = quaternion.x, quaternion.y, quaternion.z, quaternion.w
        return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
