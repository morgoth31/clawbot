"""File d'images : profondeur 1, BEST_EFFORT, dernière image seulement (REQ-PERC-014)."""
from __future__ import annotations

import numpy as np
import pytest


@pytest.mark.req("REQ-PERC-014")
def test_abonnement_profondeur_un_best_effort():
    from rclpy.qos import ReliabilityPolicy

    from yolo_node.noeud import QOS_IMAGE

    assert QOS_IMAGE.depth == 1
    assert QOS_IMAGE.reliability == ReliabilityPolicy.BEST_EFFORT


@pytest.mark.req("REQ-PERC-014")
def test_image_remplacee_pas_mise_en_file():
    from yolo_node.posttraitement import DerniereImage

    tampon = DerniereImage()
    for indice in range(5):
        tampon.deposer(np.full((4, 4, 3), indice, dtype=np.uint8), float(indice))
    assert tampon.remplacees == 4                 # quatre images écrasées

    image, horodatage = tampon.prendre()
    assert horodatage == 4.0
    assert int(image[0, 0, 0]) == 4               # la plus récente, pas la première
    assert tampon.a_traiter() is False            # rien de neuf à traiter


@pytest.mark.req("REQ-PERC-014")
def test_le_noeud_se_construit_avec_un_backend_factice():
    import rclpy

    from yolo_node.backend import BackendFactice
    from yolo_node.noeud import YoloNode

    if not rclpy.ok():
        rclpy.init()
    noeud = YoloNode(backend=BackendFactice())
    try:
        assert noeud.sub_image.qos_profile.depth == 1
        assert noeud.pub_detections.topic_name == "/perception/detections"
        assert noeud.pub_json.topic_name == "/detections"
    finally:
        noeud.destroy_node()


@pytest.mark.req("REQ-PERC-014")
def test_encodage_yuv422_donne_trois_canaux():
    """La caméra du poignet publie en yuv422 : 2 octets/pixel, pas 3 (constat déploiement)."""
    from yolo_node.noeud import vers_bgr

    image = vers_bgr(bytes(640 * 480 * 2), 480, 640, "yuv422")
    assert image is not None
    assert image.shape == (480, 640, 3)
