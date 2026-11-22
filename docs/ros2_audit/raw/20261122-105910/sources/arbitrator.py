"""Arbitre réflexe du Système 1 : propriétaire unique de la sortie actionneurs.

20 Hz, aucune allocation en boucle, aucune planification. Il lit /cmd_vel (demande), /scan,
/voltage, /imu et /arm/servo_angles, et publie la consigne réellement exécutable sur
/cmd_vel_safe. Le driver n'écoute plus que ce topic : un seul écrivain par actionneur.
"""
import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, LaserScan
from std_msgs.msg import Bool, Float32, Int32MultiArray, String

from .thresholds import battery_state, is_stale, obstacle_stop, tilt_state

CMD_TIMEOUT_S = 0.5   # au-delà, la dernière commande est périmée et remise à zéro


def _rpy(q):
    sinr = 2.0000000 * (q.w * q.x + q.y * q.z)
    cosr = 1.0 - 2.0 * (q.x * q.x + q.y * q.y)
    roll = math.degrees(math.atan2(sinr, cosr))
    sinp = max(-1.0, min(1.0, 2.0 * (q.w * q.y - q.z * q.x)))
    return roll, math.degrees(math.asin(sinp))


def decide(cmd, front_m, roll, pitch, servo2, samples, age_scan, age_imu):
    """Décision pure : l'état de sécurité et la consigne à publier."""
    moving = any(abs(v) > 1e-6 for v in (cmd[0], cmd[1], cmd[2]))
    if is_stale(age_scan) or is_stale(age_imu):
        return "SENSOR_STALE", (0.0, 0.0, 0.0)
    if obstacle_stop(front_m, moving):
        return "STOP", (0.0, 0.0, 0.0)
    etat = tilt_state(roll, pitch, servo2)
    if etat != "ok":
        # HOLD, DROP_TORQUE ou FREEZE : l'aval doit pouvoir distinguer « maintenir » de
        # « couper le couple », ce ne sont pas les mêmes gestes sur le bras.
        return etat.upper(), (0.0, 0.0, 0.0)
    if battery_state(samples, time.time()) == "low":
        return "BATTERY_LOW", (0.0, 0.0, 0.0)
    return "OK", cmd


class Arbitrator(Node):
    def __init__(self):
        super().__init__("safety_arbitrator")
        self.cmd = (0.0, 0.0, 0.0)
        self.front = float("nan")
        self.roll = 0.0
        self.pitch = 0.0
        self.servo2 = 96.0
        self.samples = []
        self.age_scan = 99.0
        self.age_imu = 99.0
        self.pub_safe = self.create_publisher(Twist, "/cmd_vel_safe", 10)
        self.pub_hold = self.create_publisher(Bool, "/safety/hold", 10)
        self.pub_state = self.create_publisher(String, "/safety/state", 10)
        self.create_subscription(Twist, "/cmd_vel", self.on_cmd, 10)
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)
        self.create_subscription(Float32, "/voltage", self.on_volt, 10)
        self.create_subscription(Imu, "/imu/data_raw", self.on_imu, 20)
        self.create_subscription(Int32MultiArray, "/arm/servo_angles", self.on_arm, 10)
        self.last_scan = self.last_imu = 0.0
        self.last_cmd = 0.0
        self.create_timer(0.05, self.tick)

    def on_cmd(self, msg):
        self.cmd = (msg.linear.x, msg.linear.y, msg.angular.z)
        self.last_cmd = time.time()

    def on_scan(self, msg):
        vals = [r for r, a in zip(msg.ranges, [msg.angle_min + msg.angle_increment * i
                                               for i in range(len(msg.ranges))])
                if abs(a) < math.radians(20) and msg.range_min < r < msg.range_max]
        if vals:
            self.front = min(vals)
        self.last_scan = time.time()

    def on_volt(self, msg):
        self.samples.append(float(msg.data))
        del self.samples[:-100]

    def on_imu(self, msg):
        self.roll, self.pitch = _rpy(msg.orientation)
        self.last_imu = time.time()

    def on_arm(self, msg):
        if len(msg.data) >= 2 and 0 <= msg.data[1] <= 180:
            self.servo2 = float(msg.data[1])

    def tick(self):
        if not getattr(self, "_log_premier", False):
            self._log_premier = True
            self.get_logger().info("premier tick de l'arbitre")
        now = time.time()
        self.age_scan = now - self.last_scan if self.last_scan else 99.0
        self.age_imu = now - self.last_imu if self.last_imu else 99.0
        # chien de garde : sans commande fraîche, la consigne ne se perpétue pas
        cmd = self.cmd if (self.last_cmd and now - self.last_cmd < CMD_TIMEOUT_S) else (0.0, 0.0, 0.0)
        etat, (vx, vy, wz) = decide(cmd, self.front, self.roll, self.pitch,
                                    self.servo2, self.samples, self.age_scan, self.age_imu)
        out = Twist()
        out.linear.x, out.linear.y, out.angular.z = vx, vy, wz
        self.pub_safe.publish(out)
        self.pub_hold.publish(Bool(data=etat != "OK"))
        self.pub_state.publish(String(data=etat))
        self._n = getattr(self, "_n", 0) + 1
        if self._n % 100 == 0:
            self.get_logger().info(f"tick {self._n} etat={etat} cmd={vx:.3f}")


def main():
    rclpy.init()
    node = Arbitrator()
    node.get_logger().info("arbitre pret, entree dans spin")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()   # SIGINT a déjà pu fermer le contexte
