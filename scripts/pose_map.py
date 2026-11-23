#!/usr/bin/env python3
"""Pose du robot dans le repere `map`, moyennee — lecture seule, aucun message publie.

Sert a mesurer la fermeture de boucle : on releve la pose au depart, puis au retour sur
le meme point physique. L'ecart est la reponse du SLAM a la question « suis-je revenu ? ».

    ROS_DOMAIN_ID=28 /usr/bin/python3 pose_map.py --seconds 3 --label "depart"
"""
from __future__ import annotations

import argparse
import json
import math
import time

import rclpy
import tf2_ros
from rclpy.node import Node


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--label", default="")
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args()

    rclpy.init()
    n = Node("hermes_pose_map")
    tampon = tf2_ros.Buffer()
    tf2_ros.TransformListener(tampon, n)
    echantillons: list[tuple[float, float, float]] = []

    debut = time.monotonic()
    while time.monotonic() - debut < args.timeout + args.seconds:
        rclpy.spin_once(n, timeout_sec=0.05)
        if time.monotonic() - debut > args.timeout:
            try:
                tr = tampon.lookup_transform("map", "base_link", rclpy.time.Time())
            except Exception:  # noqa: BLE001
                continue
            t = tr.transform.translation
            q = tr.transform.rotation
            yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            echantillons.append((t.x, t.y, yaw))
            if len(echantillons) and time.monotonic() - debut > args.timeout + args.seconds:
                break
    n.destroy_node()
    rclpy.shutdown()

    if not echantillons:
        print(json.dumps({"label": args.label, "erreur": "pas de TF map -> base_link"},
                         ensure_ascii=False))
        return 1
    k = len(echantillons)
    ys = sum(math.sin(e[2]) for e in echantillons) / k
    yc = sum(math.cos(e[2]) for e in echantillons) / k
    print(json.dumps({
        "label": args.label,
        "n": k,
        "x": round(sum(e[0] for e in echantillons) / k, 4),
        "y": round(sum(e[1] for e in echantillons) / k, 4),
        "yaw_deg": round(math.degrees(math.atan2(ys, yc)), 2),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
