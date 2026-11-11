#!/usr/bin/env python3
"""Sonde de base pour le lot 1 : mouvement court, surveillé, avec arrêt garanti.

Sécurités, dans l'ordre où elles coupent :
  - obstacle devant (lidar, ±15°) sous `--min-clear` (défaut 0,30 m) ;
  - tension sous 10,8 V ;
  - vitesse mesurée > 1,6 × consigne + 0,08 m/s sur 5 échantillons ;
  - plus de 0,5 s sans message /odom ;
  - fin de durée, ou interruption (SIGINT/SIGTERM).
Dans tous les cas, `finally` publie la vitesse nulle pendant 1 s.

    ROS_DOMAIN_ID=28 python3 scripts/base_probe_l1.py --speed 0.06 --duration 3 --out /tmp/probe.csv
"""
import argparse
import csv
import math
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float32


class Probe(Node):
    def __init__(self, min_clear, voltage_floor):
        super().__init__("base_probe_l1")
        self.min_clear = min_clear
        self.voltage_floor = voltage_floor
        self.front = None
        self.voltage = None
        self.pose = (0.0, 0.0, 0.0)
        self.measured_vx = 0.0
        self.last_odom = 0.0
        self.rows = []
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)
        self.create_subscription(Float32, "/voltage", self.on_voltage, 10)
        self.create_subscription(Odometry, "/odom", self.on_odom, 20)
        self.create_subscription(Twist, "/vel_raw", self.on_vel, 20)

    def on_scan(self, msg):
        closest = [r for r, a in zip(msg.ranges, [msg.angle_min + msg.angle_increment * i
                                                  for i in range(len(msg.ranges))])
                   if abs(a) < math.radians(15) and msg.range_min < r < msg.range_max]
        if closest:
            self.front = min(closest)

    def on_voltage(self, msg):
        self.voltage = float(msg.data)

    def on_odom(self, msg):
        q = msg.pose.pose.orientation
        yaw = math.degrees(math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                                      1.0 - 2.0 * (q.y * q.y + q.z * q.z)))
        self.pose = (msg.pose.pose.position.x, msg.pose.pose.position.y, yaw)
        self.last_odom = time.time()

    def on_vel(self, msg):
        self.measured_vx = float(msg.linear.x)

    def command(self, vx):
        msg = Twist()
        msg.linear.x = float(vx)
        self.pub.publish(msg)

    def stop_and_hold(self, seconds=1.0):
        end = time.time() + seconds
        while time.time() < end:
            self.command(0.0)
            rclpy.spin_once(self, timeout_sec=0.05)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--speed", type=float, default=0.06)
    parser.add_argument("--duration", type=float, default=3.0)
    parser.add_argument("--min-clear", type=float, default=0.30)
    parser.add_argument("--out", default="/tmp/probe_l1.csv")
    args = parser.parse_args(argv)

    rclpy.init()
    node = Probe(args.min_clear, 10.8)
    reason = "fin de duree"
    try:
        # attente des premiers messages
        deadline = time.time() + 5.0
        while time.time() < deadline and (node.front is None or node.voltage is None):
            rclpy.spin_once(node, timeout_sec=0.1)
        if node.front is None or node.voltage is None:
            reason = "capteurs muets : aucun mouvement commande"
        elif node.front < args.min_clear:
            reason = f"obstacle a {node.front:.2f} m : aucun mouvement commande"
        elif node.voltage < node.voltage_floor:
            reason = f"tension {node.voltage:.2f} V trop basse : aucun mouvement commande"
        else:
            start = time.time()
            overspeed = 0
            while time.time() - start < args.duration:
                node.command(args.speed)
                rclpy.spin_once(node, timeout_sec=0.05)
                node.rows.append([round(time.time() - start, 3), *node.pose,
                                  node.measured_vx, args.speed, node.front or 0.0])
                if node.front is not None and node.front < args.min_clear:
                    reason = f"obstacle a {node.front:.2f} m pendant le mouvement"
                    break
                if node.voltage is not None and node.voltage < node.voltage_floor:
                    reason = f"tension {node.voltage:.2f} V pendant le mouvement"
                    break
                if time.time() - node.last_odom > 0.5:
                    reason = "plus de /odom depuis 0,5 s"
                    break
                if abs(node.measured_vx) > 1.6 * args.speed + 0.08:
                    overspeed += 1
                    if overspeed >= 5:
                        reason = f"vitesse mesuree {node.measured_vx:.2f} m/s non conforme"
                        break
                else:
                    overspeed = 0
    except (KeyboardInterrupt, SystemExit):
        reason = "interruption"
    finally:
        node.stop_and_hold(1.0)
        with open(args.out, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["t_s", "x_m", "y_m", "yaw_deg", "vx_mesure", "vx_consigne", "front_m"])
            writer.writerows(node.rows)
        node.destroy_node()
        rclpy.shutdown()

    distance = math.hypot(node.pose[0], node.pose[1])
    print(f"arret  : {reason}")
    print(f"distance parcourue : {distance:.3f} m")
    print(f"pose finale : x={node.pose[0]:.3f} y={node.pose[1]:.3f} yaw={node.pose[2]:.2f} deg")
    print(f"echantillons : {len(node.rows)} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
