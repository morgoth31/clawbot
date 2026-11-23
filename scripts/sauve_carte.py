#!/usr/bin/env python3
"""Sauvegarde /map en PGM + YAML au format map_server, en maitrisant le QoS.

Le `map_saver` interne de slam_toolbox rend `result=255` en rejeu (« Failed to spin map
subscription », exactement 2 s de timeout). Cette version s'abonne en TRANSIENT_LOCAL,
attend un message, et ecrit les fichiers de facon deterministe.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


def main() -> int:
    if len(sys.argv) < 2:
        print("usage : sauve_carte.py <chemin_sans_extension> [timeout_s]")
        return 2
    base = Path(sys.argv[1])
    delai = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0

    rclpy.init()
    noeud = Node("sauve_carte")
    recu: dict[str, OccupancyGrid] = {}
    qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)
    noeud.create_subscription(OccupancyGrid, "/map", lambda m: recu.setdefault("m", m), qos)

    fin = time.time() + delai
    while "m" not in recu and time.time() < fin:
        rclpy.spin_once(noeud, timeout_sec=0.2)
    noeud.destroy_node()
    rclpy.shutdown()

    carte = recu.get("m")
    if carte is None:
        print("aucune carte recue sur /map")
        return 1

    largeur = carte.info.width
    hauteur = carte.info.height
    resolution = carte.info.resolution
    donnees = carte.data
    pixels = bytearray(largeur * hauteur)
    for i, valeur in enumerate(donnees):
        if valeur < 0:
            pixels[i] = 205
        else:
            pixels[i] = max(0, min(255, 255 - int(round(valeur * 255 / 100))))

    with (base.with_suffix(".pgm")).open("wb") as flux:
        flux.write(f"P5\n{largeur} {hauteur}\n255\n".encode())
        flux.write(bytes(pixels))

    origine = carte.info.origin.position
    (base.with_suffix(".yaml")).write_text(
        f"image: {base.name}.pgm\n"
        "mode: trinary\n"
        f"resolution: {resolution}\n"
        f"origin: [{origine.x:.3f}, {origine.y:.3f}, 0.000]\n"
        "negate: 0\n"
        "occupied_thresh: 0.65\n"
        "free_thresh: 0.25\n",
        encoding="utf-8")

    connus = sum(1 for v in donnees if v >= 0)
    occupes = sum(1 for v in donnees if v >= 50)
    print(f"carte ecrite : {largeur}x{hauteur} a {resolution} m "
          f"({largeur * hauteur * resolution ** 2:.1f} m2), "
          f"connues {connus} ({100 * connus / len(donnees):.1f} %), occupees {occupes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
