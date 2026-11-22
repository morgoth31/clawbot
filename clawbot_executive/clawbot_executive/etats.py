"""État partagé lu par les skills : capacités, sûreté, odométrie, angles du bras.

Un skill ne crée pas ses propres abonnements (P08 §5.1) : le serveur tient cet
objet, les skills le lisent.
"""
from __future__ import annotations

import json
import math
import time
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
    # Angles de servo lus par le pilote (6 valeurs, degrés) et leur date de réception.
    servo_angles: list[int] | None = None
    servo_stamp: float | None = None
    # Début de l'invalidité courante (`-1` ou hors [0, 270]), pour REQ-ARM-005.
    debut_invalide: float | None = None

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

    # ── bras ─────────────────────────────────────────────────────────────────
    def maj_servo_angles(self, valeurs, maintenant: float | None = None) -> None:
        """Reçoit `/arm/servo_angles` et date l'invalidité d'un retour muet.

        `maintenant` est injectable : les tests simulent une panne sans attendre.
        """
        instant = time.monotonic() if maintenant is None else float(maintenant)
        try:
            self.servo_angles = [int(v) for v in valeurs]
        except (TypeError, ValueError):
            self.servo_angles = None
        self.servo_stamp = instant

        from .bras import retour_servo_invalide

        if retour_servo_invalide(self.servo_angles) is None:
            self.debut_invalide = None
        elif self.debut_invalide is None:
            self.debut_invalide = instant

    def age_servo(self, maintenant: float | None = None) -> float | None:
        """Secondes depuis le dernier message d'angles, ou None s'il n'y en a jamais eu."""
        if self.servo_stamp is None:
            return None
        instant = time.monotonic() if maintenant is None else float(maintenant)
        return max(0.0, instant - self.servo_stamp)

    def duree_invalide(self, maintenant: float | None = None) -> float:
        """Durée de l'invalidité courante du retour servo (0 si tout est valide)."""
        if self.debut_invalide is None:
            return 0.0
        instant = time.monotonic() if maintenant is None else float(maintenant)
        return max(0.0, instant - self.debut_invalide)

    @staticmethod
    def lacet(quaternion) -> float:
        x, y, z, w = quaternion.x, quaternion.y, quaternion.z, quaternion.w
        return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
