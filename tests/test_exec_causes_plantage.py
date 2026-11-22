"""REQ-EXEC-023 — les deux causes de plantage du 2026-11-22 restent couvertes.

Causes établies au diagnostic C03 :

1. `clawbot-skill-server`, 18:49 — `AttributeError: 'ServeurSkills' object has no
   attribute '_sur_detections'`, levée dans le constructeur (serveur.py:136). Le code a
   été corrigé depuis, mais rien n'instanciait le constructeur : la panne n'a été vue
   qu'au déploiement, sur une copie obsolète d'`install/`.
2. `clawbot-yolo`, 18:48 — `RuntimeError: … expected input[1, 2, 480, 640] to have 3
   channels, but got 2 channels instead` : la caméra du poignet publie en `yuv422_yuy2`
   et une conversion `reshape(h, w, -1)` donne deux canaux.

Ces tests figent les deux comportements : ils échouent sur le code d'avant la correction.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "clawbot_executive"))
sys.path.insert(0, str(RACINE / "yolo_node"))


@pytest.mark.req("REQ-EXEC-023")
def test_le_serveur_de_skills_se_construit():
    """Instancie le constructeur : c'est là que `_sur_detections` manquait."""
    if os.environ.get("ROS_DOMAIN_ID") != "98":
        pytest.skip("test rclpy : domaine 98 requis")
    import rclpy

    from clawbot_executive.serveur import ServeurSkills

    if not rclpy.ok():
        rclpy.init()
    serveur = ServeurSkills()
    try:
        # Les abonnements construits dans __init__ existent : c'est leur nom qui avait
        # changé sans que l'usage suive.
        assert hasattr(serveur, "_detections")
        assert hasattr(serveur, "_detections_stamp")
        assert not hasattr(serveur, "_sur_detections")
    finally:
        serveur.destroy_node()


@pytest.mark.req("REQ-EXEC-023")
def test_une_image_yuv422_donne_trois_canaux():
    """La caméra du poignet publie en 2 octets par pixel : l'inférence veut 3 canaux."""
    numpy = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")

    from yolo_node.noeud import vers_bgr

    hauteur, largeur = 4, 6
    # yuv422_yuy2 : 2 octets par pixel, luminance + chrominance entrelacées.
    donnees = numpy.tile(numpy.array([120, 90], dtype=numpy.uint8), hauteur * largeur)
    image = vers_bgr(donnees.tobytes(), hauteur, largeur, "yuv422_yuy2")
    assert image is not None, "image non convertie"
    assert image.shape == (hauteur, largeur, 3), (
        f"attendu 3 canaux pour l'inférence, obtenu {image.shape} — c'est le "
        "RuntimeError du 2026-11-22 : expected input[1, 2, 480, 640] to have 3 channels")
    assert image.dtype == numpy.uint8
    assert cv2 is not None
