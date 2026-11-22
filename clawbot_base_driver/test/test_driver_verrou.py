"""Verrou du port série : un seul propriétaire (P03, REQ-DRV-004)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.mark.req("REQ-DRV-004")
def test_verrou_refuse_un_second_processus(tmp_path):
    """La seconde prise lève PortBusyError, avec le chemin et le PID du détenteur."""
    from clawbot_base_driver.port_lock import PortBusyError, PortLock

    verrou = tmp_path / "clawbot-mcu.lock"

    premier = PortLock(str(verrou))
    premier.acquerir()
    try:
        second = PortLock(str(verrou))
        with pytest.raises(PortBusyError) as erreur:
            second.acquerir()
        message = str(erreur.value)
        assert str(verrou) in message, f"chemin absent du message : {message!r}"
        assert str(os.getpid()) in message, f"PID du détenteur absent : {message!r}"
    finally:
        premier.relacher()

    # une fois le premier relâché, le verrou se reprend
    troisieme = PortLock(str(verrou))
    troisieme.acquerir()
    troisieme.relacher()
