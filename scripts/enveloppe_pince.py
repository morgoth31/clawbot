"""Enveloppe atteignable de arm_link5, mesuree par /compute_fk de MoveIt.

Balaye l'espace articulaire autorise (bornes lues dans le modele) et rend la position de
l'extremite du bras pour chaque echantillon. Ce n'est ni un calcul a la main ni une supposition :
c'est le modele que le planificateur utilise.
"""
import itertools

import rclpy
from moveit_msgs.srv import GetPositionFK
from rclpy.node import Node
from sensor_msgs.msg import JointState

PAS = 0.157          # 9 deg
J4 = (-1.5708, -0.7854, 0.0, 0.7854, 1.5708)

rclpy.init()
n = Node("enveloppe_pince")
cli = n.create_client(GetPositionFK, "/compute_fk")
if not cli.wait_for_service(timeout_sec=20.0):
    print("ECHEC : /compute_fk absent")
    raise SystemExit(2)

valeurs = [i * PAS for i in range(-10, 11)]
min_z = (1e9, None)
max_x = (-1e9, None)
min_z_devant = (1e9, None)
essais = 0
for j2, j3, j4 in itertools.product(valeurs, valeurs, J4):
    js = JointState()
    js.name = ["arm_joint1", "arm_joint2", "arm_joint3", "arm_joint4", "arm_joint5", "grip_joint"]
    js.position = [0.0, j2, j3, j4, 0.0, -1.54]
    req = GetPositionFK.Request()
    req.header.frame_id = "base_link"
    req.fk_link_names = ["arm_link5", "rlink1", "llink1"]
    req.robot_state.joint_state = js
    fut = cli.call_async(req)
    rclpy.spin_until_future_complete(n, fut, timeout_sec=5.0)
    if not fut.done():
        continue
    rep = fut.result()
    if not rep.pose_stamped:
        continue
    essais += 1
    p = min((x.pose.position for x in rep.pose_stamped), key=lambda q: q.z)
    if p.z < min_z[0]:
        min_z = (p.z, (round(j2, 2), round(j3, 2), round(j4, 2), round(p.x, 3)))
    if p.x > max_x[0]:
        max_x = (p.x, (round(j2, 2), round(j3, 2), round(j4, 2), round(p.z, 3)))
    if p.x > 0.15 and p.z < min_z_devant[0]:
        min_z_devant = (p.z, (round(j2, 2), round(j3, 2), round(j4, 2), round(p.x, 3)))

print(f"echantillons acceptes : {essais}")
print(f"z minimal de arm_link5 : {min_z[0]:+.3f} m   (j2,j3,j4 = {min_z[1][:3]}, x = {min_z[1][3]:+.3f})")
print(f"z minimal devant (x>0,15) : {min_z_devant[0]:+.3f} m  (x = {min_z_devant[1][3]:+.3f})")
print(f"x maximal de arm_link5 : {max_x[0]:+.3f} m   (j2,j3,j4 = {max_x[1][:3]}, z = {max_x[1][3]:+.3f})")
n.destroy_node()
rclpy.try_shutdown()
