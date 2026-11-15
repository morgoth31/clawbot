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
import statistics
import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

OUTIL = "joy_teleop/calibration.py"
SORTIE_DEFAUT = "/home/jetson/clawbot/config/manette.yaml"

# Entrées déclarées par l'opérateur, dans l'ordre où la procédure les demande.
# L'ordre suit la main : boutons faciaux, menu, puis gâchettes, puis pouces.
ENTREES_DECLAREES = [
    ("A", "le bouton A (à droite)"),
    ("B", "le bouton B (en bas)"),
    ("X", "le bouton X (en haut)"),
    ("Y", "le bouton Y (à gauche)"),
    ("plus", "le bouton +"),
    ("moins", "le bouton −"),
    ("home", "le bouton Home (maison)"),
    ("T", "le bouton T s'il existe"),
    ("rond", "le bouton rond s'il existe"),
    ("light", "le bouton lumière s'il existe"),
    ("ZL", "la gâchette haute gauche (ZL)"),
    ("ZR", "la gâchette haute droite (ZR)"),
    ("L", "la gâchette basse gauche (L)"),
    ("R", "la gâchette basse droite (R)"),
    ("M1", "le bouton M1 (palette)"),
    ("M2", "le bouton M2 (palette)"),
    ("appui_stick_gauche", "un appui vertical sur le stick gauche"),
    ("appui_stick_droit", "un appui vertical sur le stick droit"),
]


AXES_DECLARES = [
    ("stick_gauche_x", 0, "droite", "le stick gauche à droite"),
    ("stick_gauche_y", 1, "haut", "le stick gauche en haut"),
    ("stick_droit_x", 2, "droite", "le stick droit à droite"),
    ("stick_droit_y", 3, "haut", "le stick droit en haut"),
    ("croix_x", 4, "droite", "la croix à droite"),
    ("croix_y", 5, "haut", "la croix en haut"),
]

# La croix est un chapeau HID, pas un potentiomètre : ses valeurs sont -1/0/+1 et sa
# zone morte doit être large, sinon elle clignote au moindre contact.
PLANCHER_ZONE_CROIX = 0.5


def echantillonner(lecteur, duree_s: float, index: int) -> list[float]:
    """Relève `index` pendant `duree_s` (au moins deux points)."""
    n = max(2, int(duree_s / 0.02))
    valeurs = []
    for _ in range(n):
        if not lecteur.lire(0.02):
            raise RuntimeError("manette déconnectée pendant la mesure")
        axes = lecteur.etat().axes
        valeurs.append(axes[index] if index < len(axes) else 0.0)
    return valeurs


def capturer_appui(lecteur, delai_s: float = 25.0) -> int | None:
    """Attend une transition 0→1 sur un bouton et rend son index.

    Rend None si le délai expire (l'entrée sera enregistrée « absente »).
    Lève RuntimeError si le périphérique disparaît : un pad qui s'endort ne doit
    pas produire un YAML où toutes les entrées sont déclarées absentes.
    """
    depart = time.monotonic()
    avant = list(lecteur.etat().boutons)
    while time.monotonic() - depart < delai_s:
        if not lecteur.lire(0.02):
            raise RuntimeError("manette déconnectée pendant la capture")
        apres = list(lecteur.etat().boutons)
        nouveaux = [i for i, v in enumerate(apres) if v and (i >= len(avant) or not avant[i])]
        if nouveaux:
            return nouveaux[0]
        avant = apres
    return None


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

    # ── phases interactives ──────────────────────────────────────────────────

    def phase_axes(self, lecteur, axes=None, duree_repos: float = 1.2,
                   duree_balayage: float = 3.0, duree_extreme: float = 0.6,
                   journal=None) -> None:
        """Trois mesures par axe : repos, débattement complet, sens.

        Le sens n'est pas une convention : il est observé en poussant dans la
        direction annoncée. C'est ce qui a coûté trois tours de manipulation le
        2026-11-15, SDL et jsdev donnant des signes opposés.
        """
        journal = journal or print
        axes = axes if axes is not None else AXES_DECLARES
        for nom, index, direction, description in axes:
            journal(f"── axe {nom} (index {index})")
            journal("  1) Ne touche à rien pendant 1 s (repos et bruit)")
            repos = echantillonner(lecteur, duree_repos, index)
            centre = statistics.fmean(repos)
            bruit = statistics.pstdev(repos) if len(repos) > 1 else 0.0

            journal("  2) Fais tourner le stick d'un cercle complet, doucement")
            balayage = echantillonner(lecteur, duree_balayage, index)
            minimum, maximum = min(balayage), max(balayage)

            journal(f"  3) Pousse à fond vers « {direction} » et maintiens 1 s")
            extreme = statistics.fmean(echantillonner(lecteur, duree_extreme, index))
            # Règle unique pour tous les axes : si la direction ANNONCÉE produit une
            # valeur brute inférieure au centre, le décodage doit inverser le signe.
            # Un axe X droitier donne « droite > centre » (pas d'inversion) ; un axe Y
            # qui donne -1 vers le haut donne « haut < centre » (inversion).
            inverser = extreme < centre

            plancher = PLANCHER_ZONE_CROIX if nom.startswith("croix") else 0.08
            zone = max(plancher, 4 * bruit)
            self.enregistrer_axe(nom, index=index, centre=centre, minimum=minimum,
                                 maximum=maximum, zone_morte=zone, inverser=inverser)
            journal(f"     centre={centre:+.3f} mini={minimum:+.3f} maxi={maximum:+.3f} "
                    f"zone={zone:.3f} inverser={inverser}")

    def phase_boutons(self, lecteur, entrees=None, delai_s: float = 25.0,
                      journal=None) -> None:
        """Un appui dicté par entrée ; index mesuré, alias ou absent enregistré."""
        journal = journal or print
        entrees = entrees if entrees is not None else ENTREES_DECLAREES
        total = len(entrees)
        for rang, (nom, description) in enumerate(entrees, 1):
            self.declarer_entree(nom)
            journal(f"[{rang}/{total}] Appuie sur : {description}")
            index = capturer_appui(lecteur, delai_s)
            if index is None:
                self.marquer_absent(nom, f"délai de {delai_s:.0f} s dépassé sans événement")
                journal("        ↳ absent : aucun événement")
                continue
            resultat = self.enregistrer_bouton(nom, index)
            if resultat == "alias":
                cible = self.donnees["aliases"][nom]
                journal(f"        ↳ même code que {cible} (index {index}) : enregistré comme alias")
            else:
                journal(f"        ↳ index {index}")

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
