"""Boucle de déplacement : proportionnelle saturée, arrêt de sûreté (REQ-EXEC-003/004).

Logique pure : l'horloge et les consignes sont injectées, la période est une
propriété de la boucle (20 Hz), donc la latence d'arrêt est bornée par construction.
"""
from __future__ import annotations

from dataclasses import dataclass

CODES_SAFETY = {
    "HOLD": "SAFETY_HOLD",
    "SAFETY_HOLD": "SAFETY_HOLD",
    "SENSOR_STALE": "SENSOR_STALE",
    "ESTOP_LATCHED": "ESTOP_LATCHED",
    "LOW_VOLTAGE": "LOW_VOLTAGE",
}


def code_safety(safety_state: str, estop_latched: bool) -> str | None:
    """Code à rendre si l'état de sûreté interdit le mouvement, sinon None."""
    if estop_latched:
        return "ESTOP_LATCHED"
    if not safety_state:
        return None
    return CODES_SAFETY.get(str(safety_state).upper())


@dataclass
class Pas:
    vitesse_mps: float
    progress: float
    termine: bool
    code: str | None = None


class Deplacement:
    """Poursuit une cible (distance ou angle) à vitesse bornée."""

    def __init__(self, cible_m: float, max_speed: float, gain: float = 1.0,
                 tolerance_m: float = 0.02, periode_s: float = 0.05):
        if cible_m == 0.0:
            raise ValueError("cible nulle : rien à parcourir")
        self.cible = abs(cible_m)
        self.signe = 1.0 if cible_m > 0 else -1.0
        self.max_speed = abs(max_speed)
        self.gain = gain
        self.tolerance = tolerance_m
        self.periode_s = periode_s

    def pas(self, avance_m: float, safety_code: str | None) -> Pas:
        if safety_code:
            return Pas(0.0, self._progress(avance_m), True, safety_code)
        erreur = self.cible - abs(avance_m)
        if erreur <= self.tolerance:
            return Pas(0.0, 1.0, True, None)
        vitesse = min(self.gain * erreur, self.max_speed)
        return Pas(self.signe * vitesse, self._progress(avance_m), False, None)

    def _progress(self, avance_m: float) -> float:
        return max(0.0, min(1.0, abs(avance_m) / self.cible))
