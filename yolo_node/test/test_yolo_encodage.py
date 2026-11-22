"""Encodage conditionnel de l'image annotée (REQ-PERC-013)."""
from __future__ import annotations

import pytest


@pytest.mark.req("REQ-PERC-013")
def test_pas_d_encodage_sans_abonne():
    from yolo_node.noeud import doit_encoder

    assert doit_encoder(0) is False


@pytest.mark.req("REQ-PERC-013")
def test_encode_seulement_avec_abonne():
    from yolo_node.noeud import doit_encoder

    assert doit_encoder(1) is True
    assert doit_encoder(3) is True
