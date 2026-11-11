"""Machine d'attention du sentinel : IDLE → WATCHING → ENGAGED.

Logique pure, horloge injectée. Elle ne juge ni la confiance ni la distance (le nœud voit les
capteurs) : elle décide **quand** une transition mérite un réveil de S2. Une transition, un
réveil — jamais un réveil par frame. L'hystérésis est double : deux frames consécutives pour
s'engager, une absence prolongée pour revenir en veille, et un cooldown par canal.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

IDLE = "IDLE"
WATCHING = "WATCHING"
ENGAGED = "ENGAGED"


@dataclass(frozen=True)
class Regles:
    frames_consecutifs: int = 2       # spec §5.3 : person sur 2 frames consécutives
    absence_s: float = 10.0           # une frame manquée ne désengage pas
    cooldown_visuel_s: float = 60.0   # spec §5.3
    cooldown_audio_s: float = 5.0     # spec §5.3


class Attention:
    def __init__(self, regles: Regles | None = None, clock=time.monotonic):
        self.regles = regles or Regles()
        self._clock = clock
        self.etat = IDLE
        self._candidats = 0
        self._derniere_presence = None
        self._derniers_reveils: dict[str, float] = {}

    # ── canaux ───────────────────────────────────────────────────────────
    def voir(self, personne: bool) -> list[dict]:
        maintenant = self._clock()
        evenements = []
        if personne:
            self._candidats += 1
            self._derniere_presence = maintenant
            if self.etat == IDLE:
                self.etat = WATCHING
                evenements.append({"type": "ETAT", "state": WATCHING})
            if self.etat == WATCHING and self._candidats >= self.regles.frames_consecutifs:
                self.etat = ENGAGED
                evenements.append({"type": "ETAT", "state": ENGAGED})
                reveil = self._reveil("VISUAL_PERSON", maintenant,
                                     self.regles.cooldown_visuel_s)
                if reveil:
                    evenements.append(reveil)
        else:
            self._candidats = 0
            if self.etat != IDLE and self._derniere_presence is not None \
                    and maintenant - self._derniere_presence >= self.regles.absence_s:
                self.etat = IDLE
                evenements.append({"type": "ETAT", "state": IDLE})
        return evenements

    def entendre(self, activite: bool) -> list[dict]:
        maintenant = self._clock()
        evenements = []
        if activite:
            self._derniere_presence = maintenant
            if self.etat != ENGAGED:
                self.etat = ENGAGED
                evenements.append({"type": "ETAT", "state": ENGAGED})
            reveil = self._reveil("AUDIO_VAD", maintenant, self.regles.cooldown_audio_s)
            if reveil:
                evenements.append(reveil)
        return evenements

    # ── interne ──────────────────────────────────────────────────────────
    def _reveil(self, source: str, maintenant: float, cooldown: float):
        dernier = self._derniers_reveils.get(source)
        if dernier is not None and maintenant - dernier < cooldown:
            return None
        self._derniers_reveils[source] = maintenant
        return {"type": "REVEIL", "source": source, "at": maintenant}
