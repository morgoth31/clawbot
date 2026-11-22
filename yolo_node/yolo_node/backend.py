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


class BackendMoteur:
    """Moteur TensorRT FP16 exécuté par le yolov5 patché (copie hors dépôt)."""

    nom = "engine"

    def __init__(self, moteur: str, depot: str = "/home/jetson/software/yolov5-7.0-trt10"):
        import sys

        import torch

        if depot not in sys.path:
            sys.path.insert(0, depot)
        from models.common import DetectMultiBackend
        from utils.augmentations import letterbox

        self._letterbox = letterbox
        self._torch = torch
        self._modele = DetectMultiBackend(moteur, device=torch.device("cuda:0"))
        self.noms = self._modele.names if isinstance(self._modele.names, dict) else dict(
            enumerate(self._modele.names))
        self._stride = int(self._modele.stride)
        self._taille = 640

    def inferer(self, image) -> list:
        from .posttraitement import detections_depuis_lignes, nms

        redimensionnee = self._letterbox(image, self._taille, stride=self._stride,
                                         auto=True)[0]
        tenseur = redimensionnee[:, :, ::-1].transpose(2, 0, 1)      # BGR -> RGB, HWC -> CHW
        tenseur = np.ascontiguousarray(tenseur)
        tenseur = self._torch.from_numpy(tenseur).to("cuda").float() / 255.0
        tenseur = tenseur.unsqueeze(0)
        sortie = self._modele(tenseur)
        if isinstance(sortie, (list, tuple)):
            sortie = sortie[0]
        lignes = sortie[0].float().cpu().numpy().tolist()
        return nms(detections_depuis_lignes(lignes, self.noms))


def charger_backend(nom: str, modele: str | None = None):
    """Choisit le backend : factice, moteur TensorRT (.engine) ou torch (.pt)."""
    if nom == "fake":
        return BackendFactice()
    if modele and str(modele).endswith(".engine"):
        return BackendMoteur(str(modele))
    return BackendTorch(modele) if modele else BackendTorch()
