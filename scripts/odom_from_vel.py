#!/usr/bin/env python3
"""Odometrie differentielle a partir de /vel_raw et du lacet IMU.

Le chassis publie /vel_raw (vitesses calculees par le MCU a partir des encodeurs)
mais aucun /odom : ce nœud integre ces vitesses et publie /odom + la TF
odom -> base_footprint, ce qui rend la cartographie possible.

- vitesse lineaire : /vel_raw.linear.(x, y) en m/s (mecanum : x et y)
- lacet : /imu/data_raw.orientation (attitude fusionnee par le MCU, trame 0x0C),
  remise a zero a la premiere mesure pour que l'odometrie demarre a 0.
- derive : integration Euler a la cadence de /vel_raw (10 Hz) ; aucune boucle
  fermee, l'erreur croit avec la distance. Adapte a des essais courts.

Usage : ros2 run ... ou python3 odom_from_vel.py
"""
import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped, Quaternion
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
from tf2_ros import TransformBroadcaster


def yaw_from_quaternion(q: Quaternion) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class OdomFromVel(Node):
    def __init__(self):
        super().__init__('odom_from_vel')
        self.x = 0.0
        self.y = 0.0
        self.yaw_offset = None
        self.yaw = 0.0
        self.last_stamp = None
        self.pub = self.create_publisher(Odometry, 'odom', 20)
        self.tf = TransformBroadcaster(self)
        self.create_subscription(Twist, 'vel_raw', self.on_vel, 20)
        self.create_subscription(Imu, 'imu/data_raw', self.on_imu, 20)

    def on_imu(self, msg):
        y = yaw_from_quaternion(msg.orientation)
        if self.yaw_offset is None:
            self.yaw_offset = y
        self.yaw = math.atan2(math.sin(y - self.yaw_offset), math.cos(y - self.yaw_offset))

    def on_vel(self, msg):
        now = self.get_clock().now()
        if self.last_stamp is None:
            self.last_stamp = now
            return
        dt = (now - self.last_stamp).nanoseconds * 1e-9
        self.last_stamp = now
        if dt <= 0.0 or dt > 0.5:
            return
        vx, vy = msg.linear.x, msg.linear.y
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        # repere robot -> repere odom
        self.x += (vx * c - vy * s) * dt
        self.y += (vx * s + vy * c) * dt

        stamp = now.to_msg()
        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_footprint'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = math.sin(self.yaw / 2.0)
        odom.pose.pose.orientation.w = math.cos(self.yaw / 2.0)
        odom.twist.twist = msg
        self.pub.publish(odom)

        t = TransformStamped()
        t.header.stamp = stamp
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.rotation.z = math.sin(self.yaw / 2.0)
        t.transform.rotation.w = math.cos(self.yaw / 2.0)
        self.tf.sendTransform(t)


def main():
    rclpy.init()
    node = OdomFromVel()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
