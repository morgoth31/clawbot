#!/usr/bin/env python3
"""Sonde un flux sensor_msgs/Image : cadence, age du message, statistiques, capture PNG.

A repondre a une seule question : ce topic publie-t-il une image *utile*, ou seulement des
messages ? Une cadence non nulle ne prouve rien a elle seule.

Usage (imperatif : /usr/bin/python3, hors venv Hermes) :
    unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
    export PATH=/usr/bin:/bin:/usr/sbin:/sbin
    export ROS_DOMAIN_ID=28 && source /opt/ros/humble/setup.bash
    /usr/bin/python3 sonde_flux_camera.py --topic /camera/color/image_raw --out /tmp/frame.png

Avec `python3` du venv Hermes, l'import echoue sur rclpy._rclpy_pybind11 (extension cpython-310).
"""
import argparse
import time

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--duration", type=float, default=6.0, help="fenetre d'ecoute en secondes")
    ap.add_argument("--out", default=None, help="chemin PNG de la premiere image recue")
    args = ap.parse_args()

    rclpy.init()
    node = Node("sonde_flux_camera")
    stamps = []
    first = {}

    def cb(msg):
        now = node.get_clock().now().nanoseconds / 1e9
        stamps.append((now, msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9))
        first.setdefault("msg", msg)

    node.create_subscription(Image, args.topic, cb, 10)
    t0 = time.time()
    while time.time() - t0 < args.duration and len(stamps) < 200:
        rclpy.spin_once(node, timeout_sec=0.2)

    if not stamps:
        print(f"ECHEC: aucun message sur {args.topic} en {args.duration:.1f} s (ROS2-ECHO-TIMEOUT)")
        rclpy.shutdown()
        return 2

    rates = 1.0 / np.diff([s[0] for s in stamps]) if len(stamps) > 1 else np.array([])
    ages = [s[0] - s[1] for s in stamps]
    msg = first["msg"]
    if msg.encoding == "yuv422_yuy2":
        # Encodage natif des caméras UVC : deux octets par pixel, luminance ET chrominance
        # entrelacées. Le lire comme une image à un seul plan donne une vignette noire et un
        # verdict « flux noir » faux — c'est arrivé sur la caméra du poignet le 2026-11-11.
        import cv2
        brute = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.width, 2)
        a = cv2.cvtColor(brute, cv2.COLOR_YUV2RGB_YUYV)
    elif msg.encoding == "rgb8":
        a = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.width, 3)
    elif msg.encoding in ("mono8", "8UC1"):
        a = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.width)
    elif msg.encoding == "16UC1":
        a = np.frombuffer(msg.data, np.uint16).reshape(msg.height, msg.width)
    else:
        a = np.frombuffer(msg.data, np.uint8)

    print(f"topic           : {args.topic}")
    print(f"frame_id        : {msg.header.frame_id or '(vide)'}")
    print(f"taille/encodage : {msg.width}x{msg.height} {msg.encoding}")
    print(f"messages        : {len(stamps)} en {args.duration:.1f} s")
    if rates.size:
        print(f"cadence         : {rates.mean():.2f} Hz (min {rates.min():.2f} / max {rates.max():.2f})")
    print(f"age du message  : {np.mean(ages):.3f} s (min {np.min(ages):.3f} / max {np.max(ages):.3f})")
    print(f"pixels          : min {a.min()} max {a.max()} moyenne {a.mean():.1f} "
          f"non nuls {np.count_nonzero(a) / a.size * 100:.1f} %")

    verdict = []
    if np.mean(ages) > 0.5:
        verdict.append("horodatage perime (flux fige ou horloge decalee)")
    if a.max() == a.min():
        verdict.append("image uniforme (flux noir/fige)")
    if len(stamps) < 3:
        verdict.append("trop peu de messages pour conclure sur la cadence")
    print("verdict         : " + ("; ".join(verdict) if verdict else "flux exploitable"))

    if args.out:
        try:
            from PIL import Image as PILImage
            # `a` est en RGB (rgb8 ou converti depuis yuv422) : PIL attend du RGB, pas du BGR.
            img = a if a.dtype == np.uint8 else a
            if a.dtype == np.uint16:
                img = (np.clip(a, 0, 4000) / 4000 * 255).astype(np.uint8)
            PILImage.fromarray(img).save(args.out)
            print(f"capture         : {args.out}")
        except Exception as exc:  # noqa: BLE001 - la capture est un bonus, pas le verdict
            print(f"capture         : echec ({exc})")

    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
