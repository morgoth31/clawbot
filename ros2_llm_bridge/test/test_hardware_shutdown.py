"""Arrêt propre du service matériel (P02, REQ-OPS-011).

`hardware_service.py` n'avait pas de `main()` : `uvicorn.run` était appelé au
niveau module. Un point d'entrée explicite rend l'arrêt testable et symétrique
avec les autres nœuds maison.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hardware_service  # noqa: E402


@pytest.mark.req("REQ-OPS-011")
@pytest.mark.parametrize(
    "signal_",
    [KeyboardInterrupt, SystemExit],
    ids=["SIGINT", "SIGTERM"],
)
def test_main_sort_en_zero(monkeypatch, signal_):
    def run_qui_arrete(*_a, **_k):
        raise signal_()

    monkeypatch.setattr(hardware_service.uvicorn, "run", run_qui_arrete)
    monkeypatch.setattr(hardware_service, "_shutdown_ros", lambda: None)

    assert hardware_service.main() == 0
