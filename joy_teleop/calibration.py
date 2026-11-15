#!/usr/bin/env python3
"""Calibration de la manette : produit config/manette.yaml à partir du pad réel.

Principe non négociable : une entrée déclarée est soit **mesurée**, soit **aliasée**
sur une autre (M1 et M2 renvoient le même code que A et B sur ce pad), soit
explicitement **absente** avec sa raison. Aucun fichier n'est écrit tant que ce
n'est pas vérifié — un YAML partiel produirait un mapping silencieusement faux au
prochain démarrage du robot.

Ce module porte l'état de la collecte ; les phases interactives arrivent plus bas
(`phase_boutons`, `phase_axes`, …). La présente version ne fait que garantir le
contrat d'écriture.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from datetime import datetime
from pathlib import Path

import yaml

OUTIL = "joy_teleop/calibration.py"
SORTIE_DEFAUT = "/home/jetson/clawbot/config/manette.yaml"


class Calibration:
    """Accumule les mesures et écrit le YAML d'un seul bloc, à la fin."""

    def __init__(self, sortie: str | Path = SORTIE_DEFAUT, forcer: bool = False):
        self.sortie = Path(sortie)
        self.forcer = forcer
        self._declarees: list[str] = []
        self._traitees: set[str] = set()
        self._index_vers_nom: dict[int, str] = {}
        self.donnees: dict = {
            "schema": 1,
            "genere_le": datetime.now().astimezone().isoformat(timespec="seconds"),
            "outil": OUTIL,
            "poste": socket.gethostname(),
            "appareil": {},
            "boutons": {},
            "aliases": {},
            "absents": [],
            "absents_raisons": {},
            "axes": {},
            "capacites": {},
        }

    # ── déclaration ──────────────────────────────────────────────────────────

    def declarer_entree(self, nom: str) -> None:
        if nom not in self._declarees:
            self._declarees.append(nom)

    # ── enregistrement ───────────────────────────────────────────────────────

    def enregistrer_bouton(self, nom: str, index: int) -> str:
        """Enregistre un index. Rend « bouton » ou « alias » selon le cas."""
        deja = self._index_vers_nom.get(int(index))
        if deja is not None and deja != nom:
            self.enregistrer_alias(nom, deja)
            return "alias"
        self.donnees["boutons"][nom] = int(index)
        self._index_vers_nom[int(index)] = nom
        self._traitees.add(nom)
        return "bouton"

    def enregistrer_alias(self, nom: str, cible: str) -> None:
        self.donnees["aliases"][nom] = cible
        self._traitees.add(nom)

    def marquer_absent(self, nom: str, raison: str) -> None:
        if nom not in self.donnees["absents"]:
            self.donnees["absents"].append(nom)
        self.donnees["absents_raisons"][nom] = raison
        self._traitees.add(nom)

    def enregistrer_axe(self, nom: str, *, index: int, centre: float, minimum: float,
                        maximum: float, zone_morte: float, inverser: bool) -> None:
        self.donnees["axes"][nom] = {
            "index": int(index),
            "centre": round(float(centre), 4),
            "min": round(float(minimum), 4),
            "max": round(float(maximum), 4),
            "zone_morte": round(float(zone_morte), 4),
            "inverser": bool(inverser),
        }

    # ── contrôle et écriture ─────────────────────────────────────────────────

    def non_traitees(self) -> list[str]:
        return [n for n in self._declarees if n not in self._traitees]

    def _verifier(self) -> None:
        reste = self.non_traitees()
        if reste:
            raise RuntimeError(
                f"entrées déclarées mais ni mesurées, ni aliasées, ni absentes : {reste}")

    def ecrire_sans_fichier(self) -> None:
        """Même contrôle que `ecrire()`, sans toucher au disque (tests)."""
        self._verifier()

    def ecrire(self) -> Path:
        self._verifier()
        self.sortie.parent.mkdir(parents=True, exist_ok=True)
        if self.sortie.exists():
            horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
            sauvegarde = self.sortie.with_name(f"{self.sortie.name}.bak-{horodatage}")
            sauvegarde.write_bytes(self.sortie.read_bytes())
        temporaire = self.sortie.with_name(self.sortie.name + ".tmp")
        temporaire.write_text(
            yaml.safe_dump(self.donnees, allow_unicode=True, sort_keys=False),
            encoding="utf-8")
        os.replace(temporaire, self.sortie)
        return self.sortie


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Calibration de la manette")
    parseur.add_argument("--sortie", default=SORTIE_DEFAUT)
    parseur.add_argument("--seulement", default="tout",
                         help="boutons,axes,imu,actionneurs (virgules) ou tout")
    parseur.add_argument("--forcer", action="store_true",
                         help="passer outre les garde-fous (téléopération active)")
    args = parseur.parse_args(argv)

    print("Procédure de calibration non encore implémentée : seules les phases")
    print("d'écriture existent à ce stade (Task 5 du plan).")
    print(f"sortie prévue : {args.sortie}  |  phases : {args.seulement}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
