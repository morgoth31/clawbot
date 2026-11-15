"""Ce que le matériel expose réellement : capacités d'entrée, LEDs, vibration.

Aucune de ces fonctions ne suppose une capacité : elles lisent une source (sysfs,
/dev) et rendent un verdict, y compris « non disponible » — la calibration écrit
alors la raison exacte, jamais une valeur inventée.
"""

from __future__ import annotations

from pathlib import Path

CHEMIN_INPUT = Path("/sys/class/input")

# Codes EV_FF utiles. Bit 0x50 = FF_RUMBLE : sans lui, aucun effet de vibration
# ne peut être joué, quel que soit le nombre d'autres effets annoncés.
FF_RUMBLE = 0x50


def decoder_bitmap(texte: str) -> list[int]:
    """Codes positionnés d'un bitmap sysfs (« mots 64 bits, mot de poids fort d'abord »).

    Exemple réel du pad : « 7ffb000000000000 0 0 0 0 » → 14 codes BTN_* dont
    BTN_C absent, parce que le bit 2 du mot de poids fort n'est pas positionné.
    """
    codes: list[int] = []
    for rang, mot in enumerate(reversed(texte.split())):
        mot = mot.strip()
        if not mot:
            continue
        try:
            valeur = int(mot, 16)
        except ValueError:
            continue
        for bit in range(64):
            if valeur >> bit & 1:
                codes.append(rang * 64 + bit)
    return sorted(codes)


def chemin_sysfs(noeud: str, capacite: str) -> Path:
    """Chemin du bitmap d'une capacité pour un nœud donné (« js0 » → …/capabilities/ff)."""
    return CHEMIN_INPUT / noeud / "device" / "capabilities" / capacite


def vibration_supportee(chemin_ff: Path) -> bool:
    """Vrai si le noyau annonce FF_RUMBLE pour ce périphérique.

    Le bit prouve que l'API existe, pas que le moteur tourne : la calibration demande
    en plus une confirmation à l'opérateur et enregistre `verifie`.
    """
    try:
        codes = decoder_bitmap(chemin_ff.read_text(encoding="utf-8"))
    except OSError:
        return False
    return FF_RUMBLE in codes


def leds_du_pad(base_hid: Path) -> list[Path]:
    """Entrées LED rattachées au périphérique HID (vide si le pilote n'en expose pas)."""
    dossier = Path(base_hid) / "leds"
    if not dossier.is_dir():
        return []
    return sorted(p for p in dossier.iterdir() if p.is_dir())


def nom_du_noeud(noeud: str) -> str:
    """Nom annoncé par le pilote pour un nœud d'entrée, vide s'il est absent."""
    try:
        return (CHEMIN_INPUT / noeud / "device" / "name").read_text(encoding="utf-8").strip()
    except OSError:
        return ""
