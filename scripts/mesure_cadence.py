#!/usr/bin/python3
"""Mesure de cadence et de trou maximal sur un topic d'image (REQ-PERC-001).

Compte les messages pendant N secondes et rend la cadence moyenne et l'écart
maximal entre deux messages, sans désérialiser (raw=True).
"""
from __future__ import annotations

import argparse
import json
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image


class Compteur(Node):
    def __init__(self, topic: str) -> None:
        super().__init__("mesure_cadence")
        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT,
                         history=HistoryPolicy.KEEP_LAST)
        self.instants: list[float] = []
        self.create_subscription(Image, topic, self._sur_image, qos)

    def _sur_image(self, _message) -> None:
        self.instants.append(time.monotonic())


def main() -> int:
    parseur = argparse.ArgumentParser()
    parseur.add_argument("topic")
    parseur.add_argument("--duree", type=float, default=600.0)
    arguments = parseur.parse_args()

    rclpy.init()
    noeud = Compteur(arguments.topic)
    debut = time.monotonic()
    try:
        while time.monotonic() - debut < arguments.duree:
            rclpy.spin_once(noeud, timeout_sec=0.2)
    finally:
        duree = time.monotonic() - debut
        instants = noeud.instants
        ecarts = [b - a for a, b in zip(instants, instants[1:])]
        resultat = {
            "topic": arguments.topic,
            "duree_s": round(duree, 1),
            "messages": len(instants),
            "hz_moyen": round(len(instants) / duree, 2) if duree else 0.0,
            "ecart_max_s": round(max(ecarts), 3) if ecarts else None,
            "ecart_moyen_s": round(sum(ecarts) / len(ecarts), 4) if ecarts else None,
        }
        print(json.dumps(resultat, ensure_ascii=False))
        noeud.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
