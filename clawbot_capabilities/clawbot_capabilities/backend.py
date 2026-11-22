"""Pilotage des unités systemd (INV-08, REQ-CAPA-001).

Aucun motif de nom de processus : uniquement des noms d'unités de la liste blanche,
passés en liste d'arguments à `systemctl` (jamais de shell), avec `sudo -n` quand le
nœud ne tourne pas en root. L'autorisation vient de
`/etc/sudoers.d/clawbot-capabilities`, généré depuis le manifeste par
`scripts/gen_capability_auth.py`.
"""
from __future__ import annotations

import os
import subprocess


class ErreurBackend(RuntimeError):
    """Commande systemd en échec."""


class SystemdBackend:
    def __init__(self, timeout_s: float = 60.0):
        self.timeout_s = timeout_s
        self._prefixe = [] if os.geteuid() == 0 else ["sudo", "-n"]

    def _executer(self, *arguments: str) -> subprocess.CompletedProcess:
        argv = [*self._prefixe, "systemctl", *arguments]
        try:
            return subprocess.run(argv, check=True, capture_output=True,
                                  timeout=self.timeout_s, text=True)
        except subprocess.CalledProcessError as exc:
            raise ErreurBackend(f"{' '.join(argv)} : code {exc.returncode} "
                                f"{(exc.stderr or '').strip()[:200]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ErreurBackend(f"{' '.join(argv)} : délai de {self.timeout_s} s dépassé") from exc

    def demarrer(self, unite: str) -> None:
        self._executer("start", unite)

    def arreter(self, unite: str) -> None:
        self._executer("stop", unite)

    def est_actif(self, unite: str) -> bool:
        argv = [*self._prefixe, "systemctl", "is-active", "--quiet", unite]
        return subprocess.run(argv, check=False, capture_output=True,
                              timeout=self.timeout_s).returncode == 0


class FauxBackend(SystemdBackend):
    """Backend en mémoire, pour les tests d'intégration (domaine 99)."""

    def __init__(self, latence_s: float = 0.0):
        self.actives: set[str] = set()
        self.appels: list[tuple[str, str]] = []
        self.latence_s = latence_s

    def demarrer(self, unite: str) -> None:
        self.appels.append(("start", unite))
        self.actives.add(unite)

    def arreter(self, unite: str) -> None:
        self.appels.append(("stop", unite))
        self.actives.discard(unite)

    def est_actif(self, unite: str) -> bool:
        return unite in self.actives
