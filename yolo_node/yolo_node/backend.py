"""Backends d'inférence : GPU réel, ou factice pour les tests (P12)."""
from __future__ import annotations

import threading

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
    """Moteur TensorRT 10 exécuté sans le runtime de yolov5 (API `num_io_tensors`).

    Un `IExecutionContext` par thread, tampons préalloués à la taille des tenseurs, flux
    CUDA propre à chaque contexte. Aucun import de `models`/`utils` de yolov5 : ces modules
    sont déjà chargés depuis le dépôt d'origine par `torch.hub.load`, et leur runtime ne
    connaît pas l'API bindings de TensorRT 10 (`num_bindings` absent).
    """

    nom = "engine"
    TAILLE = 640

    def __init__(self, moteur: str) -> None:
        import threading

        import tensorrt as trt
        import torch

        self._trt = trt
        self._torch = torch
        self._verrou = threading.Lock()
        self._contextes: dict[int, dict] = {}

        with open(moteur, "rb") as fichier:
            serialise = fichier.read()
        self._logger = trt.Logger(trt.Logger.ERROR)
        self._runtime = trt.Runtime(self._logger)
        self._engine = self._runtime.deserialize_cuda_engine(serialise)
        if self._engine is None:
            raise RuntimeError(f"moteur illisible : {moteur}")

        self._entree = None
        self._sortie = None
        for indice in range(self._engine.num_io_tensors):
            nom = self._engine.get_tensor_name(indice)
            if self._engine.get_tensor_mode(nom) == trt.TensorIOMode.INPUT:
                self._entree = nom
            else:
                self._sortie = nom
        if not self._entree or not self._sortie:
            raise RuntimeError("moteur sans entrée ou sans sortie identifiable")
        self._forme_sortie = tuple(self._engine.get_tensor_shape(self._sortie))
        self.noms = NOMS_COCO

    # ── pré/post-traitement ──────────────────────────────────────────────────
    def _preparer(self, image):
        """letterbox 640×640, BGR→RGB, NCHW, /255 — même géométrie que yolov5."""
        import cv2

        hauteur, largeur = image.shape[:2]
        echelle = min(self.TAILLE / hauteur, self.TAILLE / largeur)
        h, l = int(round(hauteur * echelle)), int(round(largeur * echelle))
        redimensionnee = cv2.resize(image, (l, h), interpolation=cv2.INTER_LINEAR)
        canevas = np.full((self.TAILLE, self.TAILLE, 3), 114, dtype=np.uint8)
        haut, gauche = (self.TAILLE - h) // 2, (self.TAILLE - l) // 2
        canevas[haut:haut + h, gauche:gauche + l] = redimensionnee
        tenseur = canevas[:, :, ::-1].transpose(2, 0, 1)
        return np.ascontiguousarray(tenseur), echelle, gauche, haut

    def _contexte(self):
        """Un contexte et ses tampons par thread (TensorRT n'autorise pas le partage)."""
        identifiant = threading.get_ident()
        with self._verrou:
            if identifiant not in self._contextes:
                contexte = self._engine.create_execution_context()
                contexte.set_input_shape(self._entree, (1, 3, self.TAILLE, self.TAILLE))
                tampons = {}
                for indice in range(self._engine.num_io_tensors):
                    nom = self._engine.get_tensor_name(indice)
                    forme = tuple(contexte.get_tensor_shape(nom))
                    dtype = self._torch.float16 if self._engine.get_tensor_dtype(nom) == \
                        self._trt.DataType.HALF else self._torch.float32
                    tampon = self._torch.empty(forme, dtype=dtype, device="cuda")
                    contexte.set_tensor_address(nom, tampon.data_ptr())
                    tampons[nom] = tampon
                flux = self._torch.cuda.Stream()
                self._contextes[identifiant] = {"contexte": contexte, "tampons": tampons,
                                                "flux": flux}
            return self._contextes[identifiant]

    def inferer(self, image) -> list:
        from .posttraitement import detections_depuis_sortie_yolo, nms

        prep, echelle, gauche, haut = self._preparer(image)
        etat = self._contexte()
        entree = etat["tampons"][self._entree]
        entree.copy_(self._torch.from_numpy(prep).to("cuda").to(entree.dtype).div_(255.0)
                     .unsqueeze(0))
        etat["contexte"].execute_async_v3(stream_handle=etat["flux"].cuda_stream)
        etat["flux"].synchronize()

        sortie = etat["tampons"][self._sortie].float().cpu().numpy()
        lignes = sortie.reshape(-1, self._forme_sortie[-1])
        detections = detections_depuis_sortie_yolo(lignes, self.noms, conf_min=0.25)
        for detection in detections:                      # repasser en coordonnées image
            boite = detection["bbox"]
            for cle in ("x1", "x2"):
                boite[cle] = int(max(0, (boite[cle] - gauche) / echelle))
            for cle in ("y1", "y2"):
                boite[cle] = int(max(0, (boite[cle] - haut) / echelle))
        return nms(detections)


NOMS_COCO = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane", 5: "bus",
    6: "train", 7: "truck", 8: "boat", 9: "traffic light", 10: "fire hydrant",
    11: "stop sign", 12: "parking meter", 13: "bench", 14: "bird", 15: "cat", 16: "dog",
    17: "horse", 18: "sheep", 19: "cow", 20: "elephant", 21: "bear", 22: "zebra",
    23: "giraffe", 24: "backpack", 25: "umbrella", 26: "handbag", 27: "tie",
    28: "suitcase", 29: "frisbee", 30: "skis", 31: "snowboard", 32: "sports ball",
    33: "kite", 34: "baseball bat", 35: "baseball glove", 36: "skateboard",
    37: "surfboard", 38: "tennis racket", 39: "bottle", 40: "wine glass", 41: "cup",
    42: "fork", 43: "knife", 44: "spoon", 45: "bowl", 46: "banana", 47: "apple",
    48: "sandwich", 49: "orange", 50: "broccoli", 51: "carrot", 52: "hot dog",
    53: "pizza", 54: "donut", 55: "cake", 56: "chair", 57: "couch", 58: "potted plant",
    59: "bed", 60: "dining table", 61: "toilet", 62: "tv", 63: "laptop", 64: "mouse",
    65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave", 69: "oven",
    70: "toaster", 71: "sink", 72: "refrigerator", 73: "book", 74: "clock", 75: "vase",
    76: "scissors", 77: "teddy bear", 78: "hair drier", 79: "toothbrush",
}


def charger_backend(nom: str, modele: str | None = None):
    """Choisit le backend : factice, moteur TensorRT (.engine) ou torch (.pt)."""
    if nom == "fake":
        return BackendFactice()
    if modele and str(modele).endswith(".engine"):
        try:
            return BackendMoteur(str(modele))
        except Exception as exc:                     # noqa: BLE001 — repli explicite
            print(f"moteur TensorRT inutilisable ({exc}) : repli torch")
            return BackendTorch(str(modele).replace(".engine", ".pt"))
    return BackendTorch(modele) if modele else BackendTorch()
