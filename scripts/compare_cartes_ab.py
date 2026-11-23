#!/usr/bin/env python3
"""Compare deux cartes PGM de map_server sur des chiffres, pas a l'oeil.

Convention map_saver : 0 = occupe, 254 = libre, 205 = inconnu.
Metriques : cadre, surface theorique, cellules connues et leur part, occupees,
et surtout les occupees ISOLEES (aucun voisin occupe dans le 3x3) = proxy du bruit
d'appariement (reference : clawbot-dev-cycle/references/fusion-imu-odometrie.md).
"""
from __future__ import annotations

import sys
from pathlib import Path


def lire_pgm(chemin: Path) -> tuple[int, int, bytes]:
    brut = chemin.read_bytes()
    champs: list[bytes] = []
    i = 0
    while len(champs) < 4:
        while brut[i : i + 1].isspace():
            i += 1
        if brut[i : i + 1] == b"#":
            while brut[i : i + 1] != b"\n":
                i += 1
            continue
        debut = i
        while not brut[i : i + 1].isspace():
            i += 1
        champs.append(brut[debut:i])
    i += 1  # un seul blanc apres maxval
    magie, largeur, hauteur, maxval = champs
    if magie != b"P5":
        raise ValueError(f"{chemin} : PGM non binaire ({magie!r})")
    return int(largeur), int(hauteur), brut[i : i + int(largeur) * int(hauteur)]


def analyser(chemin: Path, resolution: float) -> dict:
    largeur, hauteur, pixels = lire_pgm(chemin)
    n = largeur * hauteur
    # Convention map_saver : 0 = occupe, 254 = libre, 205 = INCONNU. Une cellule connue
    # est donc libre OU occupee ; 205 ne l'est pas (piege : 205 < 250).
    libre = [v >= 250 for v in pixels]
    occupe = [v < 50 for v in pixels]
    connu = [lib or occ for lib, occ in zip(libre, occupe)]

    isolees = 0
    for y in range(hauteur):
        for x in range(largeur):
            if not occupe[y * largeur + x]:
                continue
            voisin = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < hauteur and 0 <= xx < largeur:
                        if occupe[yy * largeur + xx]:
                            voisin = True
                            break
                if voisin:
                    break
            if not voisin:
                isolees += 1

    return {
        "fichier": chemin.name,
        "largeur": largeur,
        "hauteur": hauteur,
        "surface_m2": largeur * hauteur * resolution * resolution,
        "connues": sum(connu),
        "part_connues": 100.0 * sum(connu) / n,
        "libres": sum(libre),
        "occupees": sum(occupe),
        "occupees_isolees": isolees,
        "part_isolees": 100.0 * isolees / max(1, sum(occupe)),
        "densite_utile": sum(connu) * resolution * resolution,
    }


def main() -> int:
    if len(sys.argv) < 3:
        print("usage : compare_cartes_ab.py carte_A.pgm carte_B.pgm [resolution]")
        return 2
    res = float(sys.argv[3]) if len(sys.argv) > 3 else 0.05
    a, b = (analyser(Path(p), res) for p in sys.argv[1:3])
    cles = ["largeur", "hauteur", "surface_m2", "connues", "part_connues", "libres",
            "occupees", "occupees_isolees", "part_isolees", "densite_utile"]
    print(f"{'metrique':<20}{'A':>12}{'B':>12}{'B-A':>12}{'ecart %':>10}")
    for k in cles:
        va, vb = a[k], b[k]
        delta = vb - va
        pct = 100.0 * delta / va if va else float("nan")
        if isinstance(va, float):
            colonnes = f"{va:>12.1f}{vb:>12.1f}{delta:>+12.1f}"
        else:
            colonnes = f"{va:>12d}{vb:>12d}{delta:>+12d}"
        print(f"{k:<20}{colonnes}{pct:>9.1f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
