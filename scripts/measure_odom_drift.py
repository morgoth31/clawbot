#!/usr/bin/env python3
"""Critère de sortie du lot 1 : dérive de l'odométrie sur une ligne droite.

Deux usages :
  - calcul seul, depuis un fichier de points (x, y, yaw_deg) — utilisé par les tests ;
  - enregistrement live de /odom pendant l'essai physique sur le domaine 28.

    ROS_DOMAIN_ID=28 python3 scripts/measure_odom_drift.py --record 20 --out /tmp/ligne2m.json
"""
import argparse
import json
import math
import sys


def measure_drift(samples):
    """Dérive latérale relative à la distance parcourue, en pourcentage."""
    if len(samples) < 2:
        return {"distance_m": 0.0, "lateral_m": 0.0, "yaw_deg": 0.0, "drift_pct": 0.0}
    xs = [s[0] for s in samples]
    ys = [s[1] for s in samples]
    distance = max(xs) - min(xs)
    lateral = max(abs(y) for y in ys)
    yaw = abs(samples[-1][2])
    drift = (lateral / distance * 100.0) if distance > 0 else float("inf")
    return {"distance_m": round(distance, 4), "lateral_m": round(lateral, 4),
            "yaw_deg": round(yaw, 3), "drift_pct": round(drift, 3)}


def record(seconds):
    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.node import Node

    rclpy.init()
    node = Node("measure_odom_drift")
    samples = []

    def on_odom(msg):
        q = msg.pose.pose.orientation
        yaw = math.degrees(math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                                      1.0 - 2.0 * (q.y * q.y + q.z * q.z)))
        samples.append([msg.pose.pose.position.x, msg.pose.pose.position.y, yaw])

    node.create_subscription(Odometry, "/odom", on_odom, 20)
    end = node.get_clock().now().nanoseconds + int(seconds * 1e9)
    while node.get_clock().now().nanoseconds < end:
        rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_node()
    rclpy.shutdown()
    return samples


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="JSON de points [[x, y, yaw_deg], ...]")
    parser.add_argument("--record", type=float, help="Enregistrer /odom pendant N secondes")
    parser.add_argument("--out", help="Écrire les points enregistrés dans ce fichier")
    args = parser.parse_args(argv)

    if args.record:
        samples = record(args.record)
        if args.out:
            with open(args.out, "w") as handle:
                json.dump(samples, handle)
    elif args.input:
        with open(args.input) as handle:
            samples = json.load(handle)
    else:
        parser.error("--input ou --record est requis")

    result = measure_drift(samples)
    print(json.dumps(result, indent=2))
    print("VERDICT:", "CONFORME" if result["drift_pct"] < 5.0 else "DERIVE TROP FORTE")
    return 0 if result["drift_pct"] < 5.0 else 1


if __name__ == "__main__":
    sys.exit(main())
