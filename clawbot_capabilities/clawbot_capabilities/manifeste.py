"""Manifeste des capacités : lecture et validation (REQ-CAPA-001, REQ-OPS-030).

Le manifeste est la liste blanche : rien ne se démarre hors de lui. La validation
est stricte (champ inconnu = erreur) pour qu'une faute de frappe ne devienne pas
une capacité silencieusement inerte.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CHAMPS_CAPACITE = {"units", "requires", "conflicts", "always_on", "managed",
                   "ready_when", "timeout_s", "description"}
CHAMPS_SONDE = {"topic": {"min_hz", "max_age_s"}, "action": set()}


class ErreurManifeste(ValueError):
    """Manifeste invalide : on refuse de démarrer plutôt que de deviner."""


@dataclass
class Capacite:
    nom: str
    units: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    always_on: bool = False
    managed: bool = True
    ready_when: list[dict] = field(default_factory=list)
    timeout_s: float = 30.0
    description: str = ""

    def unites_pour_arret(self) -> list[str]:
        """Ordre d'arrêt : l'inverse de l'ordre de démarrage."""
        return list(reversed(self.units))


class Manifeste(dict):
    """Capacités indexées par nom, dans l'ordre du fichier."""


def _valider_sonde(nom: str, sonde: dict) -> dict:
    if not isinstance(sonde, dict) or not sonde:
        raise ErreurManifeste(f"{nom} : entrée ready_when invalide ({sonde!r})")
    if "topic" in sonde:
        autorises = CHAMPS_SONDE["topic"]
        inconnus = set(sonde) - autorises - {"topic"}
        if inconnus:
            raise ErreurManifeste(f"{nom} : champ inconnu dans ready_when : {sorted(inconnus)}")
        if "min_hz" not in sonde and "max_age_s" not in sonde:
            raise ErreurManifeste(f"{nom} : ready_when sur {sonde['topic']} sans min_hz ni max_age_s")
        return dict(sonde)
    if "action" in sonde:
        inconnus = set(sonde) - {"action"}
        if inconnus:
            raise ErreurManifeste(f"{nom} : champ inconnu dans ready_when : {sorted(inconnus)}")
        return dict(sonde)
    raise ErreurManifeste(f"{nom} : ready_when sans topic ni action ({sonde!r})")


def charger(chemin: str | Path) -> Manifeste:
    document = yaml.safe_load(Path(chemin).read_text(encoding="utf-8")) or {}
    brut = document.get("capacites")
    if not isinstance(brut, dict) or not brut:
        raise ErreurManifeste(f"{chemin} : clé « capacites » absente ou vide")

    manifeste = Manifeste()
    for nom, donnees in brut.items():
        if not isinstance(donnees, dict):
            raise ErreurManifeste(f"{nom} : description attendue, {type(donnees).__name__} reçu")
        inconnus = set(donnees) - CHAMPS_CAPACITE
        if inconnus:
            raise ErreurManifeste(f"{nom} : champ inconnu : {sorted(inconnus)}")
        manifeste[nom] = Capacite(
            nom=nom,
            units=list(donnees.get("units") or []),
            requires=list(donnees.get("requires") or []),
            conflicts=list(donnees.get("conflicts") or []),
            always_on=bool(donnees.get("always_on", False)),
            managed=bool(donnees.get("managed", True)),
            ready_when=[_valider_sonde(nom, s) for s in (donnees.get("ready_when") or [])],
            timeout_s=float(donnees.get("timeout_s", 30.0)),
            description=str(donnees.get("description", "")),
        )

    for nom, capacite in manifeste.items():
        for unite in capacite.units:
            if not unite.endswith(".service"):
                raise ErreurManifeste(f"{nom} : « {unite} » n'est pas une unité systemd")
        for dependance in capacite.requires:
            if dependance not in manifeste:
                raise ErreurManifeste(f"{nom} : capacité requise inconnue « {dependance} »")
            if dependance == nom:
                raise ErreurManifeste(f"{nom} : dépend d'elle-même")
        for autre in capacite.conflicts:
            if autre not in manifeste:
                raise ErreurManifeste(f"{nom} : conflit avec une capacité inconnue « {autre} »")
            if nom not in manifeste[autre].conflicts:
                raise ErreurManifeste(f"{nom} : conflit avec {autre} non réciproque")
        if capacite.always_on and not capacite.units:
            raise ErreurManifeste(f"{nom} : always_on sans unité à maintenir")
    return manifeste
