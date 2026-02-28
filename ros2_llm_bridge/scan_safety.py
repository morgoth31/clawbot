#!/usr/bin/env python3
"""
scan_safety.py — LiDAR safety monitor for Clawbot.

Subscribes to /scan (sensor_msgs/LaserScan) on ROS_DOMAIN_ID=28,
computes minimum distances in 4 sectors, and writes /tmp/lidar_safety.json
every ~0.2 s so that hardware_service.py can allow/block motion.

JSON format:
{
    "timestamp": 1234567890.123,
    "safe_to_move": {"forward": true, "backward": true, "left": true, "right": true},
    "distances":    {"front": 1.5,   "back": 2.1,      "left": 0.9, "right": 1.2}
}

Run:
    source /opt/ros/humble/setup.bash
    ROS_DOMAIN_ID=28 python3 scan_safety.py

Or inside the slam tmux session (preferred):
    ros2 run ... (launch file will set domain)
"""

import json
import math
import os
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan

SAFETY_FILE   = os.getenv("SAFETY_FILE", "/tmp/lidar_safety.json")
MIN_DIST      = float(os.getenv("LIDAR_MIN_DIST", "0.35"))   # metres
ROS_DOMAIN_ID = int(os.getenv("ROS_DOMAIN_ID", "28"))

# Sector angle ranges (degrees, relative to robot front = 0°)
# Front:  -30° to +30°
# Back:   150° to 210° (i.e. -210° to -150°)
# Left:    30° to 150°
# Right: -150° to -30°
SECTORS = {
    "front": (-30, 30),
    "left":  (30, 150),
    "back":  (150, 210),
    "right": (210, 330),
}


def _angle_in_sector(angle_deg: float, lo: float, hi: float) -> bool:
    """Check if angle (0–360) falls in [lo, hi]."""
    a = angle_deg % 360
    if lo <= hi:
        return lo <= a <= hi
    return a >= lo or a <= hi


class ScanSafetyNode(Node):
    def __init__(self):
        super().__init__("scan_safety_node")
        qos = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(LaserScan, "/scan", self._scan_cb, qos)
        self.get_logger().info(
            f"ScanSafetyNode ready — domain {ROS_DOMAIN_ID}, "
            f"min_dist={MIN_DIST}m, writing → {SAFETY_FILE}"
        )

    def _scan_cb(self, msg: LaserScan):
        n = len(msg.ranges)
        distances = {"front": float("inf"), "back": float("inf"),
                     "left": float("inf"), "right": float("inf")}

        for i, r in enumerate(msg.ranges):
            if not math.isfinite(r) or r < msg.range_min or r > msg.range_max:
                continue
            angle_rad = msg.angle_min + i * msg.angle_increment
            angle_deg = math.degrees(angle_rad) % 360

            for sector, (lo, hi) in SECTORS.items():
                if _angle_in_sector(angle_deg, lo, hi):
                    if r < distances[sector]:
                        distances[sector] = r

        # Replace inf with max_range for readability
        for k in distances:
            if distances[k] == float("inf"):
                distances[k] = round(float(msg.range_max), 2)
            else:
                distances[k] = round(distances[k], 3)

        safe = {
            "forward":  distances["front"] >= MIN_DIST,
            "backward": distances["back"]  >= MIN_DIST,
            "left":     distances["left"]  >= MIN_DIST,
            "right":    distances["right"] >= MIN_DIST,
        }

        payload = {
            "timestamp":   time.time(),
            "safe_to_move": safe,
            "distances":    distances,
        }

        tmp = SAFETY_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f)
        os.replace(tmp, SAFETY_FILE)  # atomic write


def main():
    os.environ.setdefault("ROS_DOMAIN_ID", str(ROS_DOMAIN_ID))
    rclpy.init()
    node = ScanSafetyNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
