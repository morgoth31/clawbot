"""Post-traitement YOLO → détections (REQ-PERC-012, REQ-PERC-014).

Aucune dépendance ROS ici : la logique est testable sans nœud ni GPU.
"""
from __future__ import annotations

import json

CONF_MIN = 0.25
IOU_MAX = 0.45


def detections_depuis_lignes(lignes, noms=None, conf_min: float = CONF_MIN) -> list:
    """Convertit des lignes YOLO (x1, y1, x2, y2, conf, cls) en détections.

    Le format de sortie est **exactement** celui que `hardware_service` relit
    (`json.loads` sur `/detections`) : ne pas le changer sans changer l'exigence.
    """
    noms = noms or {}
    detections = []
    for ligne in lignes:
        x1, y1, x2, y2, conf, cls = (float(v) for v in ligne[:6])
        if conf < conf_min:
            continue
        classe = int(cls)
        detections.append({
            "class": noms.get(classe, str(classe)),
            "class_id": classe,
            "confidence": round(conf, 3),
            "bbox": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
        })
    return detections


def detections_depuis_sortie_yolo(lignes, noms=None, conf_min: float = CONF_MIN) -> list:
    """Décode la sortie brute `(cx, cy, w, h, obj, cls…)` d'un moteur TensorRT.

    Ce n'est PAS le format de `detections_depuis_lignes` (qui reçoit déjà des xyxy) :
    confondre les deux produit des dizaines de « person » sur toute image (constaté le
    2026-11-22 avec le moteur FP16).
    """
    noms = noms or {}
    detections = []
    for ligne in lignes:
        cx, cy, w, h, obj = (float(v) for v in ligne[:5])
        scores = [float(v) for v in ligne[5:]]
        if not scores:
            continue
        classe = int(max(range(len(scores)), key=lambda i: scores[i]))
        confiance = obj * float(scores[classe])
        if confiance < conf_min:
            continue
        detections.append({
            "class": noms.get(classe, str(classe)),
            "class_id": classe,
            "confidence": round(confiance, 3),
            "bbox": {"x1": int(cx - w / 2), "y1": int(cy - h / 2),
                     "x2": int(cx + w / 2), "y2": int(cy + h / 2)},
        })
    return detections


def _iou(a: dict, b: dict) -> float:
    ax1, ay1, ax2, ay2 = a["bbox"]["x1"], a["bbox"]["y1"], a["bbox"]["x2"], a["bbox"]["y2"]
    bx1, by1, bx2, by2 = b["bbox"]["x1"], b["bbox"]["y1"], b["bbox"]["x2"], b["bbox"]["y2"]
    x1, y1 = max(ax1, bx1), max(ay1, by1)
    x2, y2 = min(ax2, bx2), min(ay2, by2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    aire = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / aire if aire > 0 else 0.0


def nms(detections: list, iou_max: float = IOU_MAX) -> list:
    """Supprime les boîtes qui se recouvrent pour une même classe."""
    gardees: list = []
    for detection in sorted(detections, key=lambda d: d["confidence"], reverse=True):
        if any(d["class_id"] == detection["class_id"] and _iou(d, detection) > iou_max
               for d in gardees):
            continue
        gardees.append(detection)
    return gardees


def json_detections(detections: list) -> str:
    """Texte publié sur `/detections` : une liste JSON, forme du corpus."""
    return json.dumps(detections)


def vers_detection2d_array(detections: list, entete, largeur: int, hauteur: int):
    """Construit un `Detection2DArray` (vision_msgs) à partir des mêmes détections."""
    # vision_msgs définit son PROPRE Pose2D : BoundingBox2D.center refuse celui de
    # geometry_msgs (« must be a sub message of type 'Pose2D' », constaté au test).
    from vision_msgs.msg import (Detection2D, Detection2DArray, ObjectHypothesisWithPose,
                                 Pose2D)

    tableau = Detection2DArray()
    tableau.header = entete
    for detection in detections:
        boite = Detection2D()
        boite.header = entete
        centre = Pose2D()          # vision_msgs/Pose2D : `position` (Point2D) + `theta`
        centre.position.x = (detection["bbox"]["x1"] + detection["bbox"]["x2"]) / 2.0
        centre.position.y = (detection["bbox"]["y1"] + detection["bbox"]["y2"]) / 2.0
        boite.bbox.center = centre
        boite.bbox.size_x = float(detection["bbox"]["x2"] - detection["bbox"]["x1"])
        boite.bbox.size_y = float(detection["bbox"]["y2"] - detection["bbox"]["y1"])
        hypothese = ObjectHypothesisWithPose()
        hypothese.hypothesis.class_id = detection["class"]
        hypothese.hypothesis.score = float(detection["confidence"])
        boite.results.append(hypothese)
        tableau.detections.append(boite)
    tableau.header.frame_id = entete.frame_id or "wrist_camera"
    return tableau


class DerniereImage:
    """Une seule place : la nouvelle image remplace l'ancienne (REQ-PERC-014)."""

    def __init__(self) -> None:
        self._image = None
        self._horodatage = 0.0
        self._traitee = -1.0
        self.remplacees = 0

    def deposer(self, image, horodatage: float) -> None:
        if self._image is not None and self._horodatage > self._traitee:
            self.remplacees += 1
        self._image = image
        self._horodatage = horodatage

    def a_traiter(self) -> bool:
        return self._image is not None and self._horodatage > self._traitee

    def prendre(self):
        if self._image is None:
            return None, 0.0
        self._traitee = self._horodatage
        return self._image, self._horodatage
