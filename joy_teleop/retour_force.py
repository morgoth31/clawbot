"""Retour de force : jouer un effet de vibration sur un périphérique evdev.

Pourquoi pas `fftest` : l'outil est interactif et, lancé avec une entrée redirigée,
il liste les effets puis reste muet — il n'envoie jamais l'effet, et on conclut à
tort que le matériel ne vibre pas. Ici l'effet est construit et joué par ioctl,
ce qui rend le résultat vérifiable par un code de retour.

Références noyau : linux/input.h, struct ff_effect (48 octets sur cette plateforme),
struct input_event (24 octets en 64 bits).
"""

from __future__ import annotations

import fcntl
import os
import struct

# _IOW('E', 0x80, struct ff_effect) : taille 0x30 = 48 octets.
EVIOCSFF = 0x40304580
# _IOW('E', 0x81, int)
EVIOCRMFF = 0x40044581

FF_RUMBLE = 0x50
EV_FF = 0x15

TAILLE_EFFET = 48
TAILLE_EVENEMENT = 24          # struct input_event en 64 bits


def effet_rumble(force_forte: int = 0x8000, force_faible: int = 0x8000,
                 duree_ms: int = 400) -> bytes:
    """Sérialise un struct ff_effect de type rumble (id -1 = alloué par le noyau)."""
    entete = struct.pack("<HhHHHHH", FF_RUMBLE, -1, 0, 0, 0, duree_ms, 0)
    charge = struct.pack("<HH", force_forte, force_faible)
    return entete + charge + bytes(TAILLE_EFFET - len(entete) - len(charge))


def evenement_ff(code: int, valeur: int) -> bytes:
    """struct input_event : timeval nul, type EV_FF, code, valeur."""
    return struct.pack("<qqHHi", 0, 0, EV_FF, code, valeur)


class RetourForce:
    """Effet de vibration éphémère, retiré du noyau à la fermeture."""

    def __init__(self, chemin_event: str):
        self.chemin = chemin_event
        self.fd = os.open(chemin_event, os.O_RDWR)
        self.identifiant: int | None = None

    def jouer(self, duree_ms: int = 400) -> int:
        """Charge l'effet, le joue, attend, le retire. Rend l'identifiant alloué."""
        tampon = bytearray(effet_rumble(duree_ms=duree_ms))
        fcntl.ioctl(self.fd, EVIOCSFF, tampon, True)
        self.identifiant = struct.unpack_from("<h", tampon, 2)[0]
        if self.identifiant < 0:
            raise OSError(f"le noyau a refusé l'effet (id {self.identifiant})")
        os.write(self.fd, evenement_ff(self.identifiant, 1))
        return self.identifiant

    def arreter(self) -> None:
        if self.identifiant is None:
            return
        try:
            os.write(self.fd, evenement_ff(self.identifiant, 0))
            fcntl.ioctl(self.fd, EVIOCRMFF, self.identifiant)
        finally:
            self.identifiant = None

    def fermer(self) -> None:
        self.arreter()
        try:
            os.close(self.fd)
        except OSError:
            pass


def jouer_rumble(chemin_event: str, duree_ms: int = 400) -> int:
    """Joue un effet court et rend l'identifiant. Lève OSError si refusé."""
    rf = RetourForce(chemin_event)
    try:
        identifiant = rf.jouer(duree_ms)
        return identifiant
    finally:
        rf.fermer()
