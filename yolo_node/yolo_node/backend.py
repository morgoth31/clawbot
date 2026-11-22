"""Backends d'inférence : GPU réel, ou factice pour les tests (P12)."""
from __future__ import annotations

import numpy as np


class BackendFactice:
    """Rend des détections déterministes, sans GPU : utilisé en test et en intégration."""

    nom = "fake"

    def __init__(self, detections=None) -> None:
        self._detections = detections or [
            {"class": "bottle", "class_id": 39, "confidence": 0.9,
             "bbox": {"x1": 10, "y1": 20, "x2": 60, "y2": 120}}]

    def inferer(self, image) -> list:
        hauteur, largeur = image.shape[:2]
        rendues = []
        for detection in self._detections:
            boite = dict(detection["bbox"])
            if boite["x2"] > largeur or boite["y2"] > hauteur:
                continue
            rendues.append({**detection, "bbox": boite})
        return rendues


class BackendTorch:
    """YOLOv5 chargé par torch, sur CUDA quand il est disponible."""

    nom = "torch"

    def __init__(self, modele: str = "/home/jetson/software/yolov5-7.0/yolov5s.pt") -> None:
        import torch

        self._torch = torch
        self._modele = torch.hub.load("/home/jetson/software/yolov5-7.0", "custom",
                                      path=modele, source="local")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._modele.to(self.device)
        self._modele.conf = 0.25
        self.noms = self._modele.names

    def inferer(self, image) -> list:
        from .posttraitement import detections_depuis_lignes, nms

        with self._torch.no_grad():
            resultat = self._modele(image)
        lignes = resultat.xyxy[0].cpu().numpy().tolist()
        return nms(detections_depuis_lignes(lignes, self.noms))


def charger_backend(nom: str, modele: str | None = None):
    if nom == "fake":
        return BackendFactice()
    return BackendTorch(modele) if modele else BackendTorch()
