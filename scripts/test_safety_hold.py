#!/usr/bin/env python3
"""Preuve de bout en bout : l'arbitre interrompt une trajectoire du bras.

En domaine 99 (jamais 28), dans un seul processus :
  - le vrai contrôleur de bras (ArmTrajectoryServer) ;
  - le vrai arbitre (Arbitrator) ;
  - un monde simulé : /imu, /scan, /voltage (pas de /cmd_vel : on ne teste que le bras).

On lance une trajectoire de 3 s, puis on incline l'IMU simulé à 13° avec servo 2 à 96° :
l'arbitre doit décider FREEZE et publier /safety/hold, le contrôleur doit annuler.
"""
import math
import threading
import time

import rclpy
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import Twist
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import Imu, JointState, LaserScan
from std_msgs.msg import Bool, Float32, Int32MultiArray
from trajectory_msgs.msg import JointTrajectoryPoint
from builtin_interfaces.msg import Duration

from clawbot_arm_controller.arm_trajectory_server import ArmTrajectoryServer
from clawbot_safety.arbitrator import Arbitrator

JOINTS = ["arm_joint1", "arm_joint2", "arm_joint3", "arm_joint4", "arm_joint5"]


def scan(distance):
    m = LaserScan()
    m.angle_min, m.angle_max = -math.pi, math.pi
    n = 181
    m.angle_increment = 2 * math.pi / (n - 1)
    m.range_min, m.range_max = 0.05, 12.0
    m.ranges = [distance] * n
    m.header.frame_id = "laser_link"
    return m


def main():
    rclpy.init()
    srv = ArmTrajectoryServer()
    arb = Arbitrator()
    fake = Node("monde_simule")
    p_imu = fake.create_publisher(Imu, "/imu/data_raw", 20)
    p_scan = fake.create_publisher(LaserScan, "/scan", 10)
    p_volt = fake.create_publisher(Float32, "/voltage", 10)
    p_cmd = fake.create_publisher(Twist, "/cmd_vel", 10)
    joints = {}
    fake.create_subscription(JointState, "/arm/joint_states",
                             lambda m: joints.update(dict(zip(m.name, m.position))), 10)
    client = ActionClient(fake, FollowJointTrajectory, "/arm_controller/follow_joint_trajectory")

    execu = MultiThreadedExecutor()
    for node in (srv, arb, fake):
        execu.add_node(node)
    threading.Thread(target=execu.spin, daemon=True).start()

    # monde sain, bras droit
    def publier(pitch_deg=0.0):
        p_scan.publish(scan(2.0))
        p_volt.publish(Float32(data=11.9))
        a = Int32MultiArray(); a.data = [76, 96, 90, 90, 90, 149]; p_cmd.publish(Twist())
        p_imu.publish(Imu())
    for _ in range(40):
        publier()
        time.sleep(0.05)

    t = time.time()
    while time.time() - t < 5 and len(joints) < 5:
        time.sleep(0.1)
    if len(joints) < 5:
        print("ECHEC : positions articulaires indisponibles")
        return 1
    depart = [joints[j] for j in JOINTS]
    arrivee = list(depart)
    arrivee[0] = depart[0] + 0.06          # ~3,4 deg sur l'axe 1, ample et lent

    if not client.wait_for_server(timeout_sec=8):
        print("ECHEC : serveur d'action absent")
        return 1

    goal = FollowJointTrajectory.Goal()
    goal.trajectory.joint_names = JOINTS
    p0 = JointTrajectoryPoint(); p0.positions = depart; p0.time_from_start = Duration(sec=0)
    p1 = JointTrajectoryPoint(); p1.positions = arrivee; p1.time_from_start = Duration(sec=3)
    goal.trajectory.points = [p0, p1]

    fut = client.send_goal_async(goal)
    end = time.time() + 10
    while not fut.done() and time.time() < end:
        time.sleep(0.05)
    handle = fut.result()
    print("objectif accepte :", handle.accepted)

    resultat = handle.get_result_async()
    time.sleep(0.5)
    print("inclinaison simulee a 13 deg -> l'arbitre doit publier hold")
    im = Imu()
    h = math.radians(13.0) / 2
    im.orientation.y = math.sin(h)
    im.orientation.w = math.cos(h)
    t0 = time.time()
    while time.time() < t0 + 1.5:
        p_imu.publish(im)
        p_scan.publish(scan(2.0))
        time.sleep(0.02)

    end = time.time() + 10
    while not resultat.done() and time.time() < end:
        time.sleep(0.05)
    if not resultat.done():
        print("ECHEC : aucun resultat, la trajectoire n'a pas rendu la main")
        return 1
    res = resultat.result().result
    print("code :", res.error_code, "| message :", res.error_string)
    texte = (res.error_string or "").lower()
    if ("annule" in texte) or ("interrompu" in texte):
        print("SUCCES : trajectoire interrompue par le reflexe")
        return 0
    print("ECHEC : la trajectoire n'a pas ete interrompue")
    return 1


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        rclpy.try_shutdown()
    raise SystemExit(code)
