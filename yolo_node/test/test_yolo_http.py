"""Compatibilité de la façade HTTP 8003 avec le corpus (REQ-PERC-015)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

CORPUS = Path(__file__).resolve().parents[2] / "tests" / "corpus" / "perc"


@pytest.mark.req("REQ-PERC-015")
def test_reponse_compatible_avec_le_corpus():
    from yolo_node.backend import BackendFactice
    from yolo_node.serveur_http import annoter, reponse_detect

    image = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = BackendFactice().inferer(image)
    corps = reponse_detect(detections, 12, image.shape, annoter(image, detections))

    for chemin in sorted(CORPUS.glob("*.json")):
        reference = json.loads(chemin.read_text(encoding="utf-8"))
        assert set(corps) == set(reference), chemin.name
        assert set(corps["frame_size"]) == set(reference["frame_size"])
        assert isinstance(corps["detection_count"], int)
        assert isinstance(corps["inference_ms"], (int, float))
        assert corps["format"] == reference["format"] == "jpeg"
        assert isinstance(corps["image_base64"], str)
        for detection in corps["detections"]:
            assert set(detection) == {"class", "class_id", "confidence", "bbox"}
            assert set(detection["bbox"]) == {"x1", "y1", "x2", "y2"}


@pytest.mark.req("REQ-PERC-015")
def test_sans_annotation_pas_de_champ_image():
    from yolo_node.serveur_http import reponse_detect

    corps = reponse_detect([], 3, (480, 640, 3), None)
    assert "image_base64" not in corps
    assert corps["detection_count"] == 0
