"""Distance d'une détection dans l'image de profondeur — partie pure."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_sentinel.depth import distance_au_centre  # noqa: E402


def test_profondeur_32f_en_metres():
    image = np.full((100, 100), 2.0, dtype=np.float32)
    assert distance_au_centre(image, "32FC1", [40, 40, 60, 60]) == 2.0


def test_profondeur_16u_convertie_des_millimetres():
    image = np.full((100, 100), 1500, dtype=np.uint16)
    assert distance_au_centre(image, "16UC1", [10, 10, 30, 30]) == 1.5


def test_les_zeros_et_nan_sont_ignores():
    image = np.zeros((50, 50), dtype=np.float32)
    image[20:31, 20:31] = 1.2
    image[25, 25] = float("nan")
    assert distance_au_centre(image, "32FC1", [15, 15, 35, 35]) == 1.2


def test_image_sans_mesure_valide_donne_none():
    assert distance_au_centre(np.zeros((50, 50), dtype=np.float32), "32FC1", [0, 0, 20, 20]) is None


def test_boite_hors_cadre_ou_absente_donne_none():
    image = np.full((20, 20), 1.0, dtype=np.float32)
    assert distance_au_centre(image, "32FC1", [200, 200, 300, 300]) is None
    assert distance_au_centre(image, "32FC1", []) is None
