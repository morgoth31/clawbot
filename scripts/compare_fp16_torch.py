#!/usr/bin/python3
"""Comparaison FP16 (moteur TensorRT) contre la référence torch, sur 20 images (P12)."""
from __future__ import annotations

import glob
import json
import sys
import time

sys.path.insert(0, "/home/jetson/clawbot/install/yolo_node/lib/python3.10/site-packages")

from yolo_node.backend import BackendMoteur, BackendTorch  # noqa: E402

IMAGES = sorted(glob.glob("/tmp/p12_images/*.jpg"))


def principal() -> int:
    import cv2

    reference = BackendTorch("/home/jetson/software/yolov5-7.0/yolov5s.pt")
    moteur = BackendMoteur("/home/jetson/models/yolov5s_fp16.engine")

    ecarts = []
    temps_ref = []
    temps_moteur = []
    desaccords = 0
    for chemin in IMAGES:
        image = cv2.imread(chemin)
        debut = time.monotonic()
        det_ref = reference.inferer(image)
        temps_ref.append((time.monotonic() - debut) * 1000)
        debut = time.monotonic()
        det_moteur = moteur.inferer(image)
        temps_moteur.append((time.monotonic() - debut) * 1000)

        classes_ref = sorted(d["class"] for d in det_ref)
        classes_moteur = sorted(d["class"] for d in det_moteur)
        if classes_ref != classes_moteur:
            desaccords += 1
            print(f"ECART {chemin}: ref={classes_ref} moteur={classes_moteur}")
            continue
        scores_ref = {d["class"]: d["confidence"] for d in det_ref}
        for detection in det_moteur:
            if detection["class"] in scores_ref:
                ecarts.append(abs(detection["confidence"] - scores_ref[detection["class"]]))

    resultat = {
        "images": len(IMAGES),
        "desaccords_de_classe": desaccords,
        "ecart_score_max": round(max(ecarts), 4) if ecarts else None,
        "ecart_score_moyen": round(sum(ecarts) / len(ecarts), 4) if ecarts else None,
        "latence_ref_p50_ms": round(sorted(temps_ref)[len(temps_ref) // 2], 1) if temps_ref else None,
        "latence_moteur_p50_ms": round(sorted(temps_moteur)[len(temps_moteur) // 2], 1)
        if temps_moteur else None,
    }
    print(json.dumps(resultat, ensure_ascii=False))
    return 0 if desaccords == 0 and (not ecarts or max(ecarts) < 0.05) else 1


if __name__ == "__main__":
    raise SystemExit(principal())
