"""Verrou exclusif du port série du MCU (P03, REQ-DRV-004).

Le port est exclusif : deux lecteurs se volent les octets sans erreur (C08).
`flock` rend la faute visible dès la seconde ouverture, avec le PID du détenteur.
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path

CHEMIN_PAR_DEFAUT = "/run/lock/clawbot-mcu.lock"


class PortBusyError(RuntimeError):
    """Le port série est déjà tenu par un autre processus."""


def chemin_verrou() -> str:
    """`/run/lock` si inscriptible, sinon `/tmp` (P03, §5.5)."""
    for dossier in ("/run/lock", "/tmp"):
        if os.access(dossier, os.W_OK):
            return os.path.join(dossier, "clawbot-mcu.lock")
    return "/tmp/clawbot-mcu.lock"


class PortLock:
    """Verrou `flock` non bloquant, avec le PID du détenteur écrit dedans."""

    def __init__(self, chemin: str | None = None):
        self.chemin = Path(chemin or chemin_verrou())
        self._fd: int | None = None

    def acquerir(self) -> "PortLock":
        fd = os.open(str(self.chemin), os.O_RDWR | os.O_CREAT, 0o666)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            tenu = ""
            try:
                tenu = self.chemin.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            os.close(fd)
            raise PortBusyError(
                f"port deja tenu : {self.chemin} (PID detenteur {tenu or 'inconnu'})"
            ) from None
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        os.fsync(fd)
        self._fd = fd
        return self

    def relacher(self) -> None:
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None
