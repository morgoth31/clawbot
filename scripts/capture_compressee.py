"""Capture une image d'un topic sensor_msgs/CompressedImage (JPEG) et l'écrit en PNG.

Sert de contrôle croisé : le décodage JPEG est fait par OpenCV, pas par notre code de conversion
YUV. Si l'image compressée montre des détails que l'image brute ne montre pas, c'est le décodage
brut qui est en cause, pas la scène.

    ROS_DOMAIN_ID=28 python3 scripts/capture_compressee.py --topic /wrist_camera/image_raw/compressed \
        --out /tmp/check.png
"""

from __future__ import annotations

import argparse
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage


def main() -> int:
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument("--topic", required=True)
    analyseur.add_argument("--out", required=True)
    analyseur.add_argument("--delai", type=float, default=8.0)
    arguments = analyseur.parse_known_args()[0]

    rclpy.init()
    noeud = Node("capture_compressee")
    recues = []

    def _garder(msg):
        recues.append(msg)

    noeud.create_subscription(CompressedImage, arguments.topic, _garder, 10)
    fin = time.monotonic() + arguments.delai
    while time.monotonic() < fin and not recues:
        rclpy.spin_once(noeud, timeout_sec=0.2)
    noeud.destroy_node()
    rclpy.try_shutdown()

    if not recues:
        print(f"aucun message sur {arguments.topic} en {arguments.delai:g} s")
        return 1
    msg = recues[-1]
    image = cv2.imdecode(np.frombuffer(msg.data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        print(f"JPEG illisible ({msg.format})")
        return 1
    cv2.imwrite(arguments.out, image)
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    print(f"taille {image.shape[1]}x{image.shape[0]} format {msg.format} octets {len(msg.data)}")
    print(f"luminance : moyenne {gris.mean():.1f} ecart-type {gris.std():.1f} "
          f"min {gris.min()} max {gris.max()}")
    print(f"nettete (variance du laplacien) : {cv2.Laplacian(gris, cv2.CV_64F).var():.1f}")
    print(f"image : {arguments.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
