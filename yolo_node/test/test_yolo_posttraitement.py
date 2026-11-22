"""Post-traitement et sérialisation /detections (REQ-PERC-012)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parents[2] / "tests" / "corpus" / "perc"


@pytest.mark.req("REQ-PERC-012")
def test_serialisation_identique_au_corpus():
    from yolo_node.posttraitement import detections_depuis_lignes, json_detections

    reference = json.loads((CORPUS / "detect_01.json").read_text(encoding="utf-8"))
    premiere = reference["detections"][0]
    bbox = premiere["bbox"]
    detections = detections_depuis_lignes(
        [[bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"], premiere["confidence"],
          premiere["class_id"]]],
        {premiere["class_id"]: premiere["class"]})

    assert detections[0]["class"] == premiere["class"]
    assert detections[0]["class_id"] == premiere["class_id"]
    assert detections[0]["confidence"] == premiere["confidence"]
    assert detections[0]["bbox"] == bbox
    # la liste JSON se relit telle que hardware_service la consomme
    relu = json.loads(json_detections(detections))
    assert relu == [detections[0]]
    assert set(relu[0]) == {"class", "class_id", "confidence", "bbox"}


@pytest.mark.req("REQ-PERC-012")
def test_seuil_de_confiance_elimine_les_boites_faibles():
    from yolo_node.posttraitement import detections_depuis_lignes

    detections = detections_depuis_lignes([[0, 0, 10, 10, 0.1, 0], [0, 0, 10, 10, 0.8, 1]],
                                          conf_min=0.25)
    assert [d["class_id"] for d in detections] == [1]


@pytest.mark.req("REQ-PERC-012")
def test_nms_garde_la_boite_la_plus_confiante():
    from yolo_node.posttraitement import detections_depuis_lignes, nms

    detections = detections_depuis_lignes(
        [[0, 0, 100, 100, 0.9, 0], [5, 5, 100, 100, 0.6, 0], [0, 0, 100, 100, 0.7, 1]])
    gardees = nms(detections)
    assert len(gardees) == 2                      # une par classe
    assert gardees[0]["confidence"] == 0.9
