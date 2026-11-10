"""Horloge contrôlable pour les tests de temporisation (debounce, cooldown, débit)."""

from __future__ import annotations


class FakeClock:
    """Horloge monotone pilotée par le test, en secondes."""

    def __init__(self, start: float = 1000.0) -> None:
        self._now = start

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        self._now += seconds
        return self._now

    def tick(self, seconds: float, count: int) -> list[float]:
        """Avance par pas et retourne les instants atteints."""
        return [self.advance(seconds) for _ in range(count)]
