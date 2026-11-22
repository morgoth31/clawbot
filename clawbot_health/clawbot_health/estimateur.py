"""Logique pure du moniteur de santé : âge, cadence, niveau (aucune dépendance ROS).

Séparer cette logique du nœud permet de la tester sur horloge simulée, sans DDS
ni désérialisation : c'est là que se jouent les seuils de REQ-HEALTH-001 à 006.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Sequence

LEVEL_OK = 0
LEVEL_WARN = 1
LEVEL_ERROR = 2


@dataclass(frozen=True)
class Flux:
    """Une entrée du manifeste `expected_flows.yaml`."""
    topic: str
    min_hz: float
    max_age_s: float
    capability: str
    critical: bool


@dataclass(frozen=True)
class EtatFlux:
    """État d'un flux à un instant donné."""
    flux: Flux
    age: float
    cadence: float
    perime: bool
    cadence_basse: bool


class EstimateurFlux:
    """Âge du dernier message et cadence sur une fenêtre glissante."""

    def __init__(self, fenetre_s: float = 5.0):
        self.fenetre_s = float(fenetre_s)
        self._arrivees: deque[float] = deque()

    def enregistrer(self, instant: float) -> None:
        instant = float(instant)
        if self._arrivees and instant < self._arrivees[-1]:
            return                     # horloge qui recule : on ignore, on ne réordonne pas
        self._arrivees.append(instant)
        self._purger(instant)

    def _purger(self, maintenant: float) -> None:
        limite = maintenant - self.fenetre_s
        while self._arrivees and self._arrivees[0] < limite:
            self._arrivees.popleft()

    def nombre(self) -> int:
        return len(self._arrivees)

    def age(self, maintenant: float) -> float:
        if not self._arrivees:
            return math.inf
        return max(0.0, float(maintenant) - self._arrivees[-1])

    def cadence(self, maintenant: float) -> float:
        """Messages par seconde sur la fenêtre ; 0 si moins de deux points."""
        self._purger(float(maintenant))
        if len(self._arrivees) < 2:
            return 0.0
        etendue = self._arrivees[-1] - self._arrivees[0]
        if etendue <= 0.0:
            return 0.0
        return (len(self._arrivees) - 1) / etendue

    def perime(self, maintenant: float, max_age_s: float) -> bool:
        return self.age(maintenant) > float(max_age_s)


def surveilles(flux: Sequence[Flux], capacites_actives: Iterable[str]) -> list[Flux]:
    """Flux dont la capacité est active : les autres ne sont pas signalés."""
    actives = set(capacites_actives)
    return [f for f in flux if f.capability in actives]


def niveau_global(etats: Iterable[EtatFlux]) -> int:
    """ERROR prime sur WARN prime sur OK (REQ-HEALTH-003)."""
    etats = list(etats)
    if any(e.perime and e.flux.critical for e in etats):
        return LEVEL_ERROR
    if any(e.perime or e.cadence_basse for e in etats):
        return LEVEL_WARN
    return LEVEL_OK
