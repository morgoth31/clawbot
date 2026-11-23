#!/usr/bin/env python3
"""Figure de comparaison de deux cartes PGM, etiquetee depuis les fichiers eux-memes.

    /usr/bin/python3 compare_cartes_figure.py A.pgm B.pgm sortie.png \
        --titre-a "A (0,5 s / 10 cm / 0,5 m)" --titre-b "B (0,1 s / 5 cm / 0,8 m)"

Les libelles ne sont jamais devines : la taille du cadre et le compte de cellules
isolees sont recalcules ici, et affiches a cote du titre fourni.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_cartes_ab import analyser, lire_pgm  # noqa: E402


def rendu(pgm: Path, resolution: float) -> tuple[np.ndarray, dict]:
    largeur, hauteur, pixels = lire_pgm(pgm)
    grille = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(hauteur, largeur)
    image = np.full((hauteur, largeur), 0.6)          # inconnu : gris
    image[grille >= 250] = 1.0                        # libre : blanc
    image[grille < 50] = 0.0                          # occupe : noir
    return image, analyser(pgm, resolution)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("sortie")
    ap.add_argument("--resolution", type=float, default=0.05)
    ap.add_argument("--titre-a", default="A")
    ap.add_argument("--titre-b", default="B")
    args = ap.parse_args()

    (img_a, met_a), (img_b, met_b) = (rendu(Path(args.a), args.resolution),
                                      rendu(Path(args.b), args.resolution))
    fig, axes = plt.subplots(1, 2, figsize=(12, 7))
    for ax, img, met, titre in ((axes[0], img_a, met_a, args.titre_a),
                                (axes[1], img_b, met_b, args.titre_b)):
        ax.imshow(img, cmap="gray", vmin=0, vmax=1, interpolation="nearest")
        ax.set_title(f"{titre}\n{met['largeur']}x{met['hauteur']} = "
                     f"{met['surface_m2']:.1f} m2 · connues {met['connues']} "
                     f"({met['part_connues']:.1f} %) · occupees isolees "
                     f"{met['occupees_isolees']}", fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle("A/B slam_toolbox — meme bag slam2d_piece, meme EKF, seuls les "
                 "parametres SLAM changent", fontsize=10)
    fig.tight_layout()
    fig.savefig(args.sortie, dpi=110)
    print(f"ecrit : {args.sortie}")
    print(f"A : isolees {met_a['occupees_isolees']} · B : {met_b['occupees_isolees']} "
          f"({100 * (met_b['occupees_isolees'] - met_a['occupees_isolees']) / met_a['occupees_isolees']:+.1f} %)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
