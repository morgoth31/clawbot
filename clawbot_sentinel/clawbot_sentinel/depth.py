"""Distance d'une détection lue dans l'image de profondeur — partie pure, testable sans ROS.

La caméra Astra publie `16UC1` (millimètres) ou `32FC1` (mètres). Le centre de la boîte n'est pas
une mesure fiable : on prend la médiane d'une petite fenêtre, en ignorant les zéros et les NaN.
"""

from __future__ import annotations

import numpy as np

FENETRE_PX = 5


def distance_au_centre(donnees, encodage: str, bbox, fenetre: int = FENETRE_PX):
    """Médiane de profondeur au centre de la boîte, en mètres, ou None si non mesurable."""
    tableau = np.asarray(donnees)
    if tableau.ndim < 2 or not bbox:
        return None
    hauteur, largeur = tableau.shape[:2]
    x1, y1, x2, y2 = (int(v) for v in bbox[:4])
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    if not (0 <= cx < largeur and 0 <= cy < hauteur):
        return None

    fenetre_arr = tableau[max(0, cy - fenetre):cy + fenetre + 1,
                          max(0, cx - fenetre):cx + fenetre + 1].astype(float)
    if "16U" in encodage.upper():
        fenetre_arr = fenetre_arr / 1000.0
    valides = fenetre_arr[np.isfinite(fenetre_arr) & (fenetre_arr > 0.0)]
    if valides.size == 0:
        return None
    return round(float(np.median(valides)), 3)
