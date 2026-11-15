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
import math
import os
import socket
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

from js_lecteur import LecteurJs, lister_manettes, trouver_noeud_imu
from manette_materiel import chemin_sysfs, leds_du_pad, vibration_supportee

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


ENTREES_GACHETTES = [
    ("L", "la gâchette basse gauche (L)"),
    ("R", "la gâchette basse droite (R)"),
    ("ZL", "la gâchette haute gauche (ZL)"),
    ("ZR", "la gâchette haute droite (ZR)"),
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


def echantillonner_tout(lecteur, duree_s: float) -> list[list[float]]:
    """Relève tous les axes pendant `duree_s` (au moins deux points)."""
    n = max(2, int(duree_s / 0.02))
    releves = []
    for _ in range(n):
        if not lecteur.lire(0.02):
            raise RuntimeError("manette déconnectée pendant la mesure")
        releves.append(list(lecteur.etat().axes))
    return releves


def surveiller_appui(lecteur, index_bouton: int, delai_s: float,
                     seuil: float = 0.2) -> dict[int, float] | None:
    """Attend l'appui de `index_bouton` et rend les axes qui ont bougé.

    Rend None si aucun axe n'a bougé de plus de `seuil` pendant l'appui : la
    gâchette est alors binaire. C'est la seule façon de trancher sans supposer.
    Lève RuntimeError si le délai expire ou si le périphérique disparaît.
    """
    depart = time.monotonic()
    reference = list(lecteur.etat().axes)
    ecarts: dict[int, float] = {}
    vu_appui = False
    while time.monotonic() - depart < delai_s:
        if not lecteur.lire(0.02):
            raise RuntimeError("manette déconnectée pendant la capture")
        etat = lecteur.etat()
        for i, valeur in enumerate(etat.axes):
            ref = reference[i] if i < len(reference) else 0.0
            if abs(valeur - ref) > seuil:
                ecarts[i] = max(ecarts.get(i, 0.0), abs(valeur - ref))
        presse = index_bouton < len(etat.boutons) and bool(etat.boutons[index_bouton])
        if presse:
            vu_appui = True
        elif vu_appui:
            break
    if not vu_appui or not ecarts:
        return None
    return ecarts


def vider_appuis(lecteur, delai_s: float = 2.0) -> None:
    """Attend que tous les boutons soient relâchés et JETTE ce qui arrive.

    Sans cette purge, un appui en retard est attribué à l'entrée suivante et toute
    la collecte se décale — c'est exactement ce qui a produit deux relevés
    incoherents le 2026-11-15.
    """
    depart = time.monotonic()
    while time.monotonic() - depart < delai_s:
        if not lecteur.lire(0.02):
            return
        if not any(lecteur.etat().boutons):
            return


def attendre_pret(lecteur, delai_s: float = 120.0, journal=None) -> int:
    """Attend un premier appui « je suis prêt » avant d'énumérer les entrées.

    Sans cette barrière, un opérateur qui commence à appuyer pendant que le premier
    délai court décale toute la collecte d'un cran : constaté le 2026-11-15, la
    séquence entière s'est retrouvée décalée d'une entrée et le YAML était faux.
    """
    journal = journal or print
    journal("Appuie sur N'IMPORTE QUEL bouton quand tu es prêt à commencer (120 s max).")
    index = capturer_appui(lecteur, delai_s)
    if index is None:
        raise RuntimeError("aucun appui pour démarrer : séquence non lancée")
    depart = time.monotonic()
    while time.monotonic() - depart < 5.0:
        if not lecteur.lire(0.02):
            raise RuntimeError("manette déconnectée pendant la préparation")
        boutons = lecteur.etat().boutons
        if index >= len(boutons) or not boutons[index]:
            break
    journal(f"Prêt — l'appui de démarrage (index {index}) est ignoré.\n")
    return index


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

    def declarer_reserve(self, nom: str, raison: str) -> None:
        """Entrée qui existe sans être un bouton du rapport HID (commutateur, etc.)."""
        self.donnees.setdefault("reserve", {})[nom] = raison
        self._traitees.add(nom)

    def enregistrer_gachette(self, nom: str, analogique: bool, axes=None) -> None:
        entree = {"analogique": bool(analogique)}
        if axes:
            entree["axes"] = axes
        self.donnees.setdefault("gachettes", {})[nom] = entree

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
                      journal=None, demarrage: bool = False,
                      cadence: float | None = None) -> None:
        """Un appui dicté par entrée ; index mesuré, alias ou absent enregistré."""
        journal = journal or print
        entrees = entrees if entrees is not None else ENTREES_DECLAREES
        if demarrage:
            attendre_pret(lecteur, journal=journal)
        total = len(entrees)
        for rang, (nom, description) in enumerate(entrees, 1):
            self.declarer_entree(nom)
            journal(f"[{rang}/{total}] Appuie sur : {description}")
            index = capturer_appui(lecteur, cadence if cadence else delai_s)
            if cadence:
                vider_appuis(lecteur)
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

    def phase_gachettes(self, lecteur, entrees=None, delai_s: float = 25.0,
                        seuil: float = 0.2, journal=None) -> None:
        """Tranche « binaire ou analogique » en observant les axes pendant l'appui."""
        journal = journal or print
        entrees = entrees if entrees is not None else ENTREES_GACHETTES
        detectes: dict[str, dict[str, float]] = {}
        for nom, description in entrees:
            if nom in self.donnees["absents"]:
                journal(f"── {nom} : déclarée absente, rien à mesurer")
                continue
            try:
                index = self.bouton(nom)
            except KeyError:
                journal(f"── {nom} : aucune mesure de bouton, ignorée")
                continue
            journal(f"── {description} (index {index}) : appuie PROGRESSIVEMENT à fond")
            ecarts = surveiller_appui(lecteur, index, delai_s, seuil)
            if ecarts:
                detectes[nom] = {str(i): round(v, 3) for i, v in sorted(ecarts.items())}
                journal(f"   ↳ axes qui bougent : {detectes[nom]} — analogique")
            else:
                journal("   ↳ aucun axe ne bouge — binaire")

        if detectes:
            self.donnees["capacites"]["gachettes_analogiques"] = {
                "disponible": True,
                "axes_detectes": detectes,
            }
        else:
            self.donnees["capacites"]["gachettes_analogiques"] = {
                "disponible": False,
                "raison": "aucun axe ne bouge pendant l'appui : gâchettes binaires",
            }

    def phase_actionneurs(self, chemin_ff=None, base_hid=None, demander=None,
                          vibrer=None, journal=None) -> None:
        """Teste ce qui peut être commandé, et enregistre ce que l'opérateur confirme.

        Le bit FF_RUMBLE prouve que l'API existe, pas que le moteur tourne : la
        confirmation humaine est enregistrée séparément dans `verifie`.
        """
        journal = journal or print
        capacites = self.donnees.setdefault("capacites", {})

        disponible = bool(chemin_ff) and vibration_supportee(Path(chemin_ff))
        verifie = False
        if disponible:
            journal("── vibration : lancement d'un effet court")
            if vibrer:
                try:
                    vibrer()
                except Exception as err:      # noqa: BLE001 — on consigne, on ne masque pas
                    journal(f"   ↳ l'effet a échoué : {err}")
            if demander:
                verifie = bool(demander("As-tu senti la vibration ? [o/n] "))
            journal(f"   ↳ confirmée par l'opérateur : {verifie}")
        capacites["vibration"] = {
            "disponible": disponible,
            "methode": "evdev EV_FF (FF_RUMBLE)",
            "verifie": verifie,
        }

        leds = leds_du_pad(Path(base_hid)) if base_hid else []
        if leds:
            capacites["lumieres"] = {
                "disponible": True,
                "entrees": [p.name for p in leds],
            }
            journal(f"── lumière : {len(leds)} entrée(s) LED exposée(s)")
        else:
            capacites["lumieres"] = {
                "disponible": False,
                "raison": "aucune entrée /sys/class/leds rattachée au pad",
            }

    def bouton(self, nom: str) -> int:
        """Index d'un bouton déjà enregistré (ou de sa cible d'alias)."""
        if nom in self.donnees["boutons"]:
            return int(self.donnees["boutons"][nom])
        if nom in self.donnees["aliases"]:
            return self.bouton(self.donnees["aliases"][nom])
        raise KeyError(nom)

    # ── contrôle et écriture ─────────────────────────────────────────────────

    def collisions(self) -> dict[int, list[str]]:
        """Index revendiqués par plusieurs noms logiques (hors alias explicites)."""
        par_index: dict[int, list[str]] = {}
        for nom, index in self.donnees["boutons"].items():
            par_index.setdefault(int(index), []).append(nom)
        return {i: noms for i, noms in par_index.items() if len(noms) > 1}

    def non_traitees(self) -> list[str]:
        return [n for n in self._declarees if n not in self._traitees]

    def _verifier(self) -> None:
        collisions = self.collisions()
        if collisions:
            detail = ", ".join(f"index {i} : {noms}" for i, noms in collisions.items())
            raise RuntimeError(
                f"deux noms logiques revendiquent le même code ({detail}) — "
                f"séquence probablement décalée, refaire la calibration")
        for nom, a in self.donnees["axes"].items():
            debattement = abs(a["max"] - a["min"])
            if debattement < 0.5:
                raise RuntimeError(
                    f"axe {nom!r} : débattement mesuré {debattement:.2f} (min {a['min']}, "
                    f"max {a['max']}) — l'axe n'a pas été balayé, refaire cette mesure")
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


BASE_HID = Path("/sys/bus/hid/devices")
VID = "057E"
PID = "2009"


def _teleop_active(lecteur_ps=None) -> bool:
    """Vrai si un nœud de téléopération tourne (il commande les servos)."""
    try:
        sortie = (lecteur_ps() if lecteur_ps else
                  subprocess.run(["ps", "-eo", "args"], capture_output=True,
                                 text=True, timeout=5).stdout)
    except (OSError, subprocess.SubprocessError):
        return False
    return "clawbot_joy_teleop.py" in sortie


def _lire_reponse(question: str) -> str:
    """Lit une réponse au clavier ; sans terminal (service, redirection), répond non."""
    try:
        return input(question)
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def reponse_booleenne(texte: str) -> bool:
    return str(texte).strip().lower() in ("o", "oui", "y", "yes", "1")


def trouver_base_hid(vid: str = VID, pid: str = PID) -> Path | None:
    """Répertoire sysfs du périphérique HID du pad (celui qui porte ses LEDs)."""
    if not BASE_HID.is_dir():
        return None
    motif = f"{vid}:{pid}".upper()
    for candidat in sorted(BASE_HID.iterdir()):
        if motif in candidat.name.upper():
            return candidat
    return None


def vibrer(noeud: str, duree_s: int = 6) -> None:
    """Joue un effet court avec fftest, sans lever si l'outil échoue.

    fftest est interactif : on lui envoie « 1 » pour jouer le premier effet.
    L'échec n'est pas une erreur de calibration — c'est l'opérateur qui tranche.
    """
    event = noeud.replace("js", "event")
    subprocess.run(["fftest", f"/dev/input/{event}"], input="1\n", text=True,
                   capture_output=True, timeout=duree_s)


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Calibration de la manette")
    parseur.add_argument("--sortie", default=SORTIE_DEFAUT)
    parseur.add_argument("--seulement", default="tout",
                         help="boutons,axes,gachettes,imu,actionneurs (virgules) ou tout")
    parseur.add_argument("--duree-appui", type=float, default=25.0,
                         help="délai par entrée avant de la déclarer absente (s)")
    parseur.add_argument("--cadence", type=float, default=0.0,
                         help="rythme imposé : un appui attendu toutes les N secondes")
    parseur.add_argument("--forcer", action="store_true",
                         help="passer outre les garde-fous (téléopération active)")
    args = parseur.parse_args(argv)

    phases = ({"boutons", "axes", "gachettes", "actionneurs"}
              if args.seulement == "tout"
              else {p.strip() for p in args.seulement.split(",") if p.strip()})

    # Garde-fou 1 : la téléopération commande les servos à chaque appui. Même
    # discipline que scripts/read_arm_angles.py face au pilote.
    if not args.forcer and _teleop_active():
        print("ERREUR : la téléopération tourne — elle commande les servos à chaque appui.")
        print("         sudo systemctl stop clawbot-joy-teleop   (ou --forcer)")
        return 3

    manettes = lister_manettes()
    if not manettes:
        print("ERREUR : aucune manette détectée sur un nœud /dev/input/jsN.")
        print("         sudo bash joy_teleop/pair_procontroller.sh, puis appuyer sur un bouton")
        return 4

    chemin_pad, nom = manettes[0]
    cal = Calibration(args.sortie, args.forcer)
    cal.donnees["appareil"] = {
        "nom": nom,
        "js_pad": chemin_pad,
        "js_imu": trouver_noeud_imu() or "",
    }
    print(f"Manette : {nom} sur {chemin_pad}")
    print(f"Sortie   : {args.sortie}")
    print(f"Phases   : {', '.join(sorted(phases))}\n")

    lecteur = LecteurJs(chemin_pad)
    try:
        if "boutons" in phases:
            print("═══ Boutons ═══")
            cal.phase_boutons(lecteur, delai_s=args.duree_appui, demarrage=True,
                              cadence=(args.cadence or None))
        if "axes" in phases:
            print("\n═══ Axes ═══")
            cal.phase_axes(lecteur)
        if "gachettes" in phases and cal.donnees["boutons"]:
            print("\n═══ Gâchettes ═══")
            cal.phase_gachettes(lecteur, delai_s=args.duree_appui)
        if "actionneurs" in phases:
            print("\n═══ Actionneurs ═══")
            noeud = chemin_pad.rsplit("/", 1)[-1]
            base_hid = trouver_base_hid()
            cal.phase_actionneurs(
                chemin_ff=chemin_sysfs(noeud, "ff"),
                base_hid=base_hid,
                demander=lambda question: reponse_booleenne(_lire_reponse(question)),
                vibrer=lambda: vibrer(noeud),
            )
    except RuntimeError as err:
        print(f"\nINTERROMPU : {err}")
        print("Aucun fichier écrit. Réveiller la manette (un appui) et relancer.")
        return 5
    finally:
        lecteur.fermer()

    chemin = cal.ecrire()
    print(f"\nÉcrit : {chemin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
