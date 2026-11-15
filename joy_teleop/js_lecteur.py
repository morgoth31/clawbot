"""Lecture d'un périphérique /dev/input/jsN : décodage de struct js_event.

Unique implémentation du protocole dans le dépôt : `js_joy_source.py` l'utilise en
temps réel, `calibration.py` l'utilise en mode guidé. Le format est décrit dans
linux/input.h (struct js_event : __u32 time, __s16 value, __u8 type, __u8 number),
le bit 0x80 de `type` marquant un événement d'initialisation qui annonce les
capacités du périphérique sans changement d'état.

Un tampon partiel est ignoré au lieu de lever : un `read()` peut rendre un nombre
d'octets non multiple de 8, et perdre l'état complet pour cela serait pire que de
retarder d'un cycle.
"""

from __future__ import annotations

import os
import select
import struct
from dataclasses import dataclass, field

EVENT_FMT = "<IhBB"
EVENT_TAILLE = struct.calcsize(EVENT_FMT)   # 8 octets
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80

# Mots à exclure du choix de périphérique : ce sont des capteurs inertiels.
EXCLUS = ("IMU", "ACCEL", "GYRO", "MAGNET", "COMPASS")


def lister_manettes() -> list[tuple[str, str]]:
    """[(chemin, nom)] des nœuds js qui ne sont pas des capteurs inertiels.

    Le pad et son IMU exposent le MÊME nom : seule l'exclusion par mot-clé permet
    de choisir le bon nœud de façon déterministe.
    """
    manettes: list[tuple[str, str]] = []
    nom = None
    try:
        with open("/proc/bus/input/devices", encoding="utf-8", errors="replace") as f:
            for ligne in f:
                if ligne.startswith("N: Name="):
                    nom = ligne[len("N: Name="):].strip().strip('"')
                elif ligne.startswith("H: Handlers="):
                    for jeton in ligne.split():
                        if jeton.startswith("js") and jeton[2:].isdigit():
                            if nom and not any(m in nom.upper() for m in EXCLUS):
                                manettes.append((f"/dev/input/{jeton}", nom))
                elif not ligne.strip():
                    nom = None
    except OSError:
        pass
    return manettes


def trouver_noeud_imu() -> str | None:
    """Chemin du premier nœud js dont le nom désigne un capteur inertiel."""
    nom = None
    try:
        with open("/proc/bus/input/devices", encoding="utf-8", errors="replace") as f:
            for ligne in f:
                if ligne.startswith("N: Name="):
                    nom = ligne[len("N: Name="):].strip().strip('"')
                elif ligne.startswith("H: Handlers="):
                    for jeton in ligne.split():
                        if jeton.startswith("js") and jeton[2:].isdigit():
                            if nom and any(m in nom.upper() for m in EXCLUS):
                                return f"/dev/input/{jeton}"
                elif not ligne.strip():
                    nom = None
    except OSError:
        pass
    return None


@dataclass
class Etat:
    """État complet d'un pad : listes pleines, trous à zéro."""

    axes: list[float] = field(default_factory=list)
    boutons: list[int] = field(default_factory=list)


def decodifier(tampon: bytes) -> list[tuple[int, int, int]]:
    """Rend [(type, numero, valeur)] pour chaque événement entier du tampon."""
    evenements = []
    for offset in range(0, len(tampon) - EVENT_TAILLE + 1, EVENT_TAILLE):
        _, valeur, etype, numero = struct.unpack_from(EVENT_FMT, tampon, offset)
        evenements.append((etype, numero, valeur))
    return evenements


class LecteurJs:
    """État courant d'un jsdev, alimenté par `ingerer()` ou par le descripteur.

    Sans chemin, aucun descripteur n'est ouvert : les tests injectent des tampons
    binaires et la calibration peut lire un fichier de capture.
    """

    def __init__(self, chemin: str | None = None):
        self.chemin = chemin
        self.fd: int | None = None
        self._axes: dict[int, float] = {}
        self._boutons: dict[int, int] = {}
        self._axes_annonces = 0
        self._boutons_annonces = 0
        if chemin:
            self.fd = os.open(chemin, os.O_RDONLY | os.O_NONBLOCK)

    def ingerer(self, tampon: bytes) -> None:
        for etype, numero, valeur in decodifier(tampon):
            init = bool(etype & JS_EVENT_INIT)
            etype &= ~JS_EVENT_INIT
            if etype == JS_EVENT_AXIS:
                if init:
                    self._axes_annonces = max(self._axes_annonces, numero + 1)
                else:
                    self._axes[numero] = valeur / 32767.0
            elif etype == JS_EVENT_BUTTON:
                if init:
                    self._boutons_annonces = max(self._boutons_annonces, numero + 1)
                else:
                    self._boutons[numero] = int(valeur)

    def lire(self, attente_s: float = 0.02) -> bool:
        """Lit ce qui est disponible. False si le périphérique a disparu."""
        if self.fd is None:
            return False
        lus, _, _ = select.select([self.fd], [], [], attente_s)
        if not lus:
            return True
        try:
            donnees = os.read(self.fd, EVENT_TAILLE * 64)
        except OSError:
            return False
        if not donnees:
            return False
        self.ingerer(donnees)
        return True

    def etat(self) -> Etat:
        n_axes = max(self._axes_annonces, (max(self._axes) + 1) if self._axes else 0)
        n_boutons = max(self._boutons_annonces, (max(self._boutons) + 1) if self._boutons else 0)
        return Etat(
            axes=[self._axes.get(i, 0.0) for i in range(n_axes)],
            boutons=[self._boutons.get(i, 0) for i in range(n_boutons)],
        )

    def fermer(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
