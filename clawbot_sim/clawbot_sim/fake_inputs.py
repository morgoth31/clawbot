"""Capteurs simulés sains pour les tests d'intégration (P04, domaine 99).

Publie /scan, /imu/data_raw, /voltage et /arm/servo_angles aux cadences C12 avec
des valeurs saines et paramétrables. Aucun éditeur de vitesse : ce nœud ne
commande rien.
"""
from __future__ import annotations

import math
import sys

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, LaserScan
from std_msgs.msg import Float32, Int32MultiArray


class FakeInputs(Node):
    def __init__(self, context=None):
        super().__init__("fake_inputs", context=context)
        self.declare_parameter("front_m", 5.0)
        self.declare_parameter("voltage", 11.9)
        self.declare_parameter("roll_deg", 0.0)
        self.declare_parameter("pitch_deg", 0.0)
        self.declare_parameter("servo2_deg", 96)

        self.front = float(self.get_parameter("front_m").value)
        self.voltage = float(self.get_parameter("voltage").value)
        self.roll = math.radians(float(self.get_parameter("roll_deg").value))
        self.pitch = math.radians(float(self.get_parameter("pitch_deg").value))
        self.servo2 = int(self.get_parameter("servo2_deg").value)

        self.pub_scan = self.create_publisher(LaserScan, "/scan", qos_profile_sensor_data)
        self.pub_imu = self.create_publisher(Imu, "/imu/data_raw", 10)
        self.pub_volt = self.create_publisher(Float32, "/voltage", 10)
        self.pub_arm = self.create_publisher(Int32MultiArray, "/arm/servo_angles", 10)

        self.create_timer(0.1, self._scan)      # 10 Hz, C12
        self.create_timer(0.1, self._imu)       # 10 Hz, C12
        self.create_timer(0.1, self._volt)      # 10 Hz, C12
        self.create_timer(0.55, self._arm)      # ~1,8 Hz, une lecture de servo par cycle

    def _scan(self):
        msg = LaserScan()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "laser_link"
        msg.angle_min = -math.pi
        msg.angle_increment = math.pi / 180.0
        msg.range_min = 0.05
        msg.range_max = 10.0
        msg.ranges = [self.front] * 360
        self.pub_scan.publish(msg)

    def _imu(self):
        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "imu_link"
        cy, sy = math.cos(self.roll / 2), math.sin(self.roll / 2)
        cp, sp = math.cos(self.pitch / 2), math.sin(self.pitch / 2)
        msg.orientation.w, msg.orientation.x = cy * cp, sy * cp
        msg.orientation.y, msg.orientation.z = cy * sp, -sy * sp
        self.pub_imu.publish(msg)

    def _volt(self):
        self.pub_volt.publish(Float32(data=self.voltage))

    def _arm(self):
        self.pub_arm.publish(Int32MultiArray(data=[2, self.servo2]))


def main():
    rclpy.init(args=sys.argv[1:])
    node = FakeInputs()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    return 0
