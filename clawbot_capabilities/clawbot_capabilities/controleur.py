"""Machine d'état des capacités (REQ-CAPA-001 à 005).

Logique pure : ni rclpy ni systemd ici. L'horloge et les sondes sont injectées, ce
qui rend chaque transition testable sans robot.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from .manifeste import Capacite, Manifeste


class Etat(str, Enum):
    INACTIVE = "INACTIVE"
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class Code(str, Enum):
    OK = "OK"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    CAPABILITY_NOT_MANAGED = "CAPABILITY_NOT_MANAGED"
    CAPABILITY_CONFLICT = "CAPABILITY_CONFLICT"
    CAPABILITY_STOP_FAILED = "CAPABILITY_STOP_FAILED"
    ALWAYS_ON = "ALWAYS_ON"
    DEPENDENCY_ACTIVE = "DEPENDENCY_ACTIVE"
    UNIT_FAILED = "UNIT_FAILED"
    READY_TIMEOUT = "READY_TIMEOUT"
    ALREADY_IN_STATE = "ALREADY_IN_STATE"


@dataclass
class Resultat:
    success: bool
    code: Code
    etat: Etat
    message: str


class Backend(Protocol):
    def demarrer(self, unite: str) -> None: ...
    def arreter(self, unite: str) -> None: ...
    def est_actif(self, unite: str) -> bool: ...


class Sonde(Protocol):
    def preter(self) -> bool: ...


class Controleur:
    """États, transitions et refus ; publie un compteur de changements."""

    def __init__(self, manifeste: Manifeste, backend: Backend | None,
                 fabrique_sondes: Callable[[Capacite], list[Sonde]],
                 horloge: Callable[[], float] = time.monotonic):
        self.manifeste = manifeste
        self.backend = backend
        self.fabrique_sondes = fabrique_sondes
        self.horloge = horloge
        self._etats = {nom: Etat.INACTIVE for nom in manifeste}
        self._debut: dict[str, float] = {}
        self._sondes: dict[str, list[Sonde]] = {}
        self.changements = 0

    # ── lecture ──────────────────────────────────────────────────────────────
    def etiquette(self, nom: str) -> Etat:
        return self._etats[nom]

    def actives(self) -> set[str]:
        return {n for n, e in self._etats.items() if e in (Etat.ACTIVE, Etat.STARTING)}

    def instantane(self) -> dict[str, dict]:
        return {
            nom: {
                "name": nom,
                "state": self._etats[nom].value,
                "units": list(self.manifeste[nom].units),
                "requires": list(self.manifeste[nom].requires),
                "conflicts": list(self.manifeste[nom].conflicts),
                "stale_flows": [],
            }
            for nom in self.manifeste
        }

    # ── écriture d'état ──────────────────────────────────────────────────────
    def _poser(self, nom: str, etat: Etat) -> None:
        if self._etats[nom] != etat:
            self._etats[nom] = etat
            self.changements += 1

    # ── demandes ─────────────────────────────────────────────────────────────
    def demander(self, nom: str, actif: bool, timeout_s: float | None = None) -> Resultat:
        if nom not in self.manifeste:
            return Resultat(False, Code.UNKNOWN_CAPABILITY, Etat.INACTIVE,
                            f"capacité inconnue : {nom!r} (liste blanche : "
                            f"{', '.join(self.manifeste)})")
        capacite = self.manifeste[nom]
        if not capacite.managed:
            return Resultat(False, Code.CAPABILITY_NOT_MANAGED, self._etats[nom],
                            f"capacité {nom} décrite mais non pilotable (managed: false)")
        if actif:
            return self._activer(capacite, timeout_s)
        return self._desactiver(capacite)

    def _activer(self, capacite: Capacite, timeout_s: float | None) -> Resultat:
        nom = capacite.nom
        if self._etats[nom] in (Etat.ACTIVE, Etat.STARTING):
            return Resultat(True, Code.ALREADY_IN_STATE, self._etats[nom],
                            f"{nom} déjà {self._etats[nom].value.lower()}")
        for autre in capacite.conflicts:
            if autre in self.actives():
                return Resultat(False, Code.CAPABILITY_CONFLICT, self._etats[nom],
                                f"{nom} est en conflit avec {autre} "
                                f"({self._etats[autre].value.lower()}) ; arrêtez-le d'abord")
        for dependance in capacite.requires:
            if self._etats[dependance] in (Etat.ACTIVE, Etat.STARTING):
                continue
            resultat = self._activer(self.manifeste[dependance], None)
            if not resultat.success:
                return resultat

        for unite in capacite.units:
            try:
                self.backend.demarrer(unite)
            except Exception as exc:                       # noqa: BLE001 - toute erreur = unité KO
                self._poser(nom, Etat.FAILED)
                return Resultat(False, Code.UNIT_FAILED, Etat.FAILED,
                                f"{nom} : démarrage de {unite} impossible ({exc})")
        self._debut[nom] = self.horloge()
        self._sondes[nom] = self.fabrique_sondes(capacite)
        self._poser(nom, Etat.STARTING)
        return Resultat(True, Code.OK, Etat.STARTING, f"{nom} : démarrage en cours")

    def _desactiver(self, capacite: Capacite) -> Resultat:
        nom = capacite.nom
        if capacite.always_on:
            return Resultat(False, Code.ALWAYS_ON, self._etats[nom],
                            f"{nom} est always_on : son arrêt n'est pas une opération de service")
        dependantes = sorted(n for n in self.actives()
                             if n != nom and nom in self.manifeste[n].requires)
        if dependantes:
            return Resultat(False, Code.DEPENDENCY_ACTIVE, self._etats[nom],
                            f"{nom} est requis par {', '.join(dependantes)} : arrêtez-les d'abord")
        if self._etats[nom] == Etat.INACTIVE:
            return Resultat(True, Code.ALREADY_IN_STATE, Etat.INACTIVE, f"{nom} déjà inactif")
        self._poser(nom, Etat.STOPPING)
        for unite in capacite.unites_pour_arret():
            try:
                self.backend.arreter(unite)
            except Exception as exc:                       # noqa: BLE001
                self._poser(nom, Etat.FAILED)
                return Resultat(False, Code.CAPABILITY_STOP_FAILED, Etat.FAILED,
                                f"{nom} : arrêt de {unite} impossible ({exc})")
        self._sondes.pop(nom, None)
        self._debut.pop(nom, None)
        self._poser(nom, Etat.INACTIVE)
        return Resultat(True, Code.OK, Etat.INACTIVE, f"{nom} : arrêté")

    # ── avancement des états transitoires ────────────────────────────────────
    def rafraichir(self) -> int:
        """Fait avancer STARTING → ACTIVE (sondes prêtes) ou FAILED (délai dépassé)."""
        avant = self.changements
        maintenant = self.horloge()
        for nom, etat in list(self._etats.items()):
            if etat != Etat.STARTING:
                continue
            capacite = self.manifeste[nom]
            sondes = self._sondes.get(nom, [])
            if sondes and all(s.preter() for s in sondes):
                self._poser(nom, Etat.ACTIVE)
                continue
            limite = self._debut.get(nom, maintenant) + capacite.timeout_s
            if maintenant >= limite:
                self._poser(nom, Etat.FAILED)
        return self.changements - avant
