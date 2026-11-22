"""Façade HTTP 8003 : mêmes routes et même forme de réponse qu'avant (REQ-PERC-015).

Servie dans le processus du nœud, elle appelle la même fonction d'inférence : une seule
implémentation, deux façades (ROS 2 et HTTP).
"""
from __future__ import annotations

import base64
import json
import os
import time

import cv2

QUALITE_JPEG = 85


def reponse_detect(detections: list, inference_ms: int, taille: tuple,
                   image_annotee=None) -> dict:
    """Corps de /detect, identique en forme au corpus du 2026-11-22."""
    hauteur, largeur = taille[:2]
    corps = {
        "camera": "claw",
        "detections": detections,
        "detection_count": len(detections),
        "inference_ms": int(inference_ms),
        "frame_size": {"width": int(largeur), "height": int(hauteur)},
    }
    if image_annotee is not None:
        ok, tampon = cv2.imencode(".jpg", image_annotee,
                                  [cv2.IMWRITE_JPEG_QUALITY, QUALITE_JPEG])
        if ok:
            corps["image_base64"] = base64.b64encode(tampon.tobytes()).decode()
            corps["format"] = "jpeg"
    return corps


def annoter(image, detections: list):
    """Dessine les boîtes sur une copie de l'image."""
    annotee = image.copy()
    for detection in detections:
        boite = detection["bbox"]
        cv2.rectangle(annotee, (boite["x1"], boite["y1"]), (boite["x2"], boite["y2"]),
                      (0, 255, 0), 2)
        etiquette = f"{detection['class']} {detection['confidence']:.2f}"
        cv2.putText(annotee, etiquette, (boite["x1"], max(boite["y1"] - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return annotee


def creer_application(infere, derniere_image):
    """Application FastAPI : `infere(image)` et `derniere_image()` sont fournis par le nœud."""
    from fastapi import FastAPI, HTTPException, Query

    application = FastAPI(title="Clawbot YOLO Inference Service", version="2.0.0")

    @application.get("/health")
    async def sante() -> dict:
        return {"status": "ok", "model_loaded": True, "backend": "ros2"}

    @application.get("/detect")
    async def detect(camera: str = Query("claw", description="Camera: 'claw' or 'front'"),
                     save: bool = Query(False),
                     annotate: bool = Query(True)) -> dict:
        if camera not in ("claw", "front"):
            raise HTTPException(400, f"Unknown camera '{camera}'")
        image = derniere_image()
        if image is None:
            raise HTTPException(503, "aucune image sur la caméra du poignet")
        debut = time.time()
        detections = infere(image)
        inference_ms = round((time.time() - debut) * 1000)
        annotee = annoter(image, detections) if annotate else None
        corps = reponse_detect(detections, inference_ms, image.shape, annotee)
        if save:
            chemin = os.path.join(os.getenv("WORKSPACE_PATH",
                                            "/home/jetson/.openclaw/workspace"),
                                  f"yolo_{camera}.jpg")
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            cv2.imwrite(chemin, annotee if annotee is not None else annoter(image, detections))
            corps["saved_path"] = chemin
        return corps

    @application.get("/model")
    async def modele() -> dict:
        return {"model": "yolov5s", "device": "cuda", "conf": 0.25}

    return application


def servir(application, port: int, hote: str = "0.0.0.0") -> None:
    """Démarre uvicorn dans le fil courant (appelé depuis un thread du nœud)."""
    import uvicorn

    uvicorn.run(application, host=hote, port=port, log_level="warning")
