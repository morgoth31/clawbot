#!/usr/bin/env python3
"""Aller-retour de cartographie, autonome et proprement terminé.

Aucun timeout externe : la séquence porte ses propres durées et publie toujours la consigne
nulle en sortie. Garde lidar sur chaque translation (arrêt sous 0,35 m).

    ROS_DOMAIN_ID=28 python3 scripts/slam_run.py --leg 1.3 --speed 0.05
"""
import argparse
import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class Run(Node):
    def __init__(self):
        super().__init__("slam_run")
        self.front = 9.0
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)

    def on_scan(self, msg):
        vals = [r for r, a in zip(msg.ranges, [msg.angle_min + msg.angle_increment * i
                                               for i in range(len(msg.ranges))])
                if abs(a) < math.radians(20) and msg.range_min < r < msg.range_max]
        if vals:
            self.front = min(vals)

    def hold(self, v, w, seconds, guard=False):
        end = time.time() + seconds
        while time.time() < end:
            msg = Twist()
            msg.linear.x = v
            msg.angular.z = w
            self.pub.publish(msg)
            rclpy.spin_once(self, timeout_sec=0.05)
            if guard and self.front < 0.35:
                return False
        return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--leg", type=float, default=1.3)
    p.add_argument("--speed", type=float, default=0.05)
    p.add_argument("--turn", type=float, default=180.0)
    p.add_argument("--spin", type=float, default=0.6)
    a = p.parse_args()

    rclpy.init()
    n = Run()
    n.hold(0.0, 0.0, 0.5)
    etats = []
    try:
        duree = a.leg / a.speed
        ok = n.hold(a.speed, 0.0, duree, guard=True)
        etats.append("aller " + ("ok" if ok else "STOP obstacle"))
        n.hold(0.0, 0.0, 0.5)
        if ok:
            n.hold(0.0, a.spin, math.radians(a.turn) / a.spin)
            etats.append("rotation ok")
            n.hold(0.0, 0.0, 0.5)
            ok = n.hold(a.speed, 0.0, duree, guard=True)
            etats.append("retour " + ("ok" if ok else "STOP obstacle"))
    finally:
        n.hold(0.0, 0.0, 1.0)
        print(" | ".join(etats))
        print("arret : consigne nulle maintenue")
        n.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
