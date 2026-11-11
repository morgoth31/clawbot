"""Poses ou la pince atteint un point ET ou la camera du poignet le voit.

La camera est montee sur `arm_link4`, a 90 deg de l'axe de la pince : une configuration qui pose les
doigts sur l'objet peut tourner l'objectif vers le plafond (constate le 2026-11-11 a la pose
d'approche : tangage +67 deg). Pour un asservissement visuel final, il faut les deux a la fois.

    python3 scripts/pose_saisie_vue.py 0.358 0.0 0.294 [--hauteur-visee 0.33]

Critere : distance pince <-> point de saisie, et distance du point a l'axe optique (le point doit
etre dans le champ, pas seulement devant l'objectif). Le modele du cadre optique est celui de
l'URDF corrige le 2026-11-11 (joint `wrist_camera_optical_joint`, rpy 0 0 -1.5708).
"""
from __future__ import annotations

import argparse
import itertools
import math
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "scripts"))

from cinematique_bras import Bras, _servo_vers_rad  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Poses saisie + visee camera")
    ap.add_argument("x", type=float)
    ap.add_argument("y", type=float)
    ap.add_argument("z", type=float, help="point de saisie (arm_link5 vise)")
    ap.add_argument("--hauteur-visee", type=float, default=None,
                    help="z du point que la camera doit viser (defaut : le point de saisie + 4 cm)")
    ap.add_argument("--tolerance", type=float, default=0.06)
    a = ap.parse_args()

    cible_pince = (a.x, a.y, a.z)
    cible_vue = (a.x, a.y, a.hauteur_visee if a.hauteur_visee is not None else a.z + 0.04)
    bras = Bras()

    resultats = []
    for j1 in (0.0,):
        for j2 in [i * 0.1 for i in range(-15, 16)]:
            for j3 in [i * 0.1 for i in range(-15, 16)]:
                for j4 in [i * 0.2 for i in range(-7, 8)]:
                    angles = {"arm_joint1": j1, "arm_joint2": j2,
                              "arm_joint3": j3, "arm_joint4": j4, "arm_joint5": 0.0}
                    p5 = bras.position(bras.pose("arm_link5", angles))
                    d_pince = math.dist(p5, cible_pince)
                    if d_pince > a.tolerance:
                        continue
                    m = bras.pose("wrist_camera_optical_frame", angles)
                    cam = bras.position(m)
                    axe = bras.axe(m, 2)
                    v = [cible_vue[i] - cam[i] for i in range(3)]
                    t = sum(v[i] * axe[i] for i in range(3))      # projection sur l'axe optique
                    if t < 0.10:                                   # objet derriere l'objectif
                        continue
                    proj = [cam[i] + t * axe[i] for i in range(3)]
                    d_vue = math.dist(proj, cible_vue)
                    tangage = math.degrees(math.asin(max(-1.0, min(1.0, axe[2]))))
                    resultats.append((d_pince + d_vue, d_pince, d_vue, t, tangage, j1, j2, j3, j4,
                                      cam, axe))

    resultats.sort()
    print(f"point de saisie {cible_pince}, point vise par la camera {cible_vue}")
    print(f"{len(resultats)} configurations satisfont pince < {a.tolerance} m")
    if not resultats:
        print("AUCUNE : la pince et la camera ne peuvent pas viser le meme point ici")
        return 1
    print(" score  pince   vue   dist_cam  tangage    j1     j2     j3     j4    cam")
    for score, dp, dv, t, tang, j1, j2, j3, j4, cam, _ in resultats[:8]:
        print(f" {score:.3f}  {dp:.3f}  {dv:.3f}   {t:.2f} m  {tang:+5.0f}   {j1:+.2f}  {j2:+.2f}  "
              f"{j3:+.2f}  {j4:+.2f}  ({cam[0]:+.3f},{cam[1]:+.3f},{cam[2]:+.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
