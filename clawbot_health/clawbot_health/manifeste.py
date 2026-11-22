"""Manifeste des flux attendus (référentiel §8)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from .estimateur import Flux

NOM = "expected_flows.yaml"


def chemin_par_defaut() -> str:
    """Chemin du manifeste installé, avec repli sur la source du dépôt."""
    try:
        from ament_index_python.packages import get_package_share_directory
        return os.path.join(get_package_share_directory("clawbot_health"), "config", NOM)
    except Exception:
        return str(Path(__file__).resolve().parents[1] / "config" / NOM)


def charger(chemin: str) -> list[Flux]:
    """Lit le manifeste et refuse une entrée incomplète plutôt que de l'ignorer."""
    document = yaml.safe_load(Path(chemin).read_text(encoding="utf-8")) or {}
    entrees = document.get("flows") or []
    if not entrees:
        raise ValueError(f"manifeste de santé vide : {chemin}")

    flux = []
    for entree in entrees:
        manquants = {"topic", "min_hz", "max_age_s", "capability", "critical"} - set(entree)
        if manquants:
            raise ValueError(f"{chemin}: entrée incomplète {sorted(manquants)} : {entree}")
        flux.append(Flux(topic=str(entree["topic"]),
                         min_hz=float(entree["min_hz"]),
                         max_age_s=float(entree["max_age_s"]),
                         capability=str(entree["capability"]),
                         critical=bool(entree["critical"])))
    return flux
