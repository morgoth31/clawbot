#!/usr/bin/env python3
"""Enregistre /odom (horodatage du message) dans un CSV — pour comparer une cap.

    ROS_DOMAIN_ID=99 /usr/bin/python3 enregistre_odom.py <sortie.csv> [duree_s]
"""
from __future__ import annotations

import math
import sys
import time

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node


def yaw_of(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def main() -> int:
    sortie = sys.argv[1]
    attendre = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    rclpy.init()
    n = Node("hermes_enregistre_odom")
    premier: list[float | None] = [None]
    with open(sortie, "w") as f:
        f.write("stamp,x,y,yaw,wz\n")

        def cb(m):
            if premier[0] is None:
                premier[0] = time.monotonic()
                n.get_logger().info("/odom publie : enregistrement en cours")
            t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
            p = m.pose.pose
            f.write(f"{t:.6f},{p.position.x:.5f},{p.position.y:.5f},"
                    f"{yaw_of(p.orientation):.6f},{m.twist.twist.angular.z:.6f}\n")

        n.create_subscription(Odometry, "/odom", cb, 50)
        debut = time.monotonic()
        while rclpy.ok():
            rclpy.spin_once(n, timeout_sec=0.2)
            # Garde : un CSV vide ne dit pas « pas de derive », il dit « rien n'a ete mesure ».
            # Un ekf_node en use_sim_time lance avant /clock ne publie jamais (saut d'horloge).
            if premier[0] is None and time.monotonic() - debut > attendre:
                print(f"ECHEC : aucun message /odom en {attendre:.0f} s — l'EKF ne publie pas. "
                      "Demarrer le bag (--clock) AVANT l'EKF, sinon il prend un saut d'horloge "
                      "et reste muet. Aucune mesure produite.", file=sys.stderr)
                n.destroy_node()
                return 2
    n.destroy_node()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
