"""Base simulée : intègre `/cmd_vel_safe` en `/odom` (mecanum) et publie un `/scan` fixe.

Sert aux tests d'intégration (domaine 99) : sans elle, un skill de déplacement
n'aurait aucune odométrie à lire. La cinématique est celle d'un X3 à roues
mecanum : vx, vy et wz sont indépendants.
"""
from __future__ import annotations

import math

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class FakeBase(Node):
    def __init__(self, periode_s: float = 0.05):
        super().__init__("fake_base")
        self.periode_s = periode_s
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.wz = 0.0
        # `bloque` : la base n'obéit plus (roue bloquée, câble arraché) — l'odométrie
        # ne bouge plus alors que les consignes continuent d'arriver.
        self.bloque = False

        self.create_subscription(Twist, "/cmd_vel_safe", self._sur_cmd, 10)
        self.pub_odom = self.create_publisher(Odometry, "/odom", 20)
        self.pub_scan = self.create_publisher(LaserScan, "/scan", 10)
        self.create_timer(periode_s, self._tick_odom)
        self.create_timer(0.1, self._tick_scan)

    def _sur_cmd(self, msg: Twist) -> None:
        self.vx, self.vy, self.wz = msg.linear.x, msg.linear.y, msg.angular.z

    def _tick_odom(self) -> None:
        if self.bloque:
            self.vx = self.vy = self.wz = 0.0
        self.x += (self.vx * math.cos(self.yaw) - self.vy * math.sin(self.yaw)) * self.periode_s
        self.y += (self.vx * math.sin(self.yaw) + self.vy * math.cos(self.yaw)) * self.periode_s
        self.yaw += self.wz * self.periode_s

        message = Odometry()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = "odom"
        message.child_frame_id = "base_footprint"
        message.pose.pose.position.x = self.x
        message.pose.pose.position.y = self.y
        message.pose.pose.orientation.z = math.sin(self.yaw / 2.0)
        message.pose.pose.orientation.w = math.cos(self.yaw / 2.0)
        message.twist.twist.linear.x = self.vx
        message.twist.twist.linear.y = self.vy
        message.twist.twist.angular.z = self.wz
        self.pub_odom.publish(message)

    def _tick_scan(self) -> None:
        message = LaserScan()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = "laser_frame"
        message.angle_min = -math.pi
        message.angle_max = math.pi
        message.angle_increment = math.pi / 180.0
        message.range_min = 0.05
        message.range_max = 12.0
        message.ranges = [3.0] * 360           # pièce dégagée de 3 m
        self.pub_scan.publish(message)
