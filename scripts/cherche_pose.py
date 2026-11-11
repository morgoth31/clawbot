"""Configuration du bras dont arm_link5 est la plus proche d'un point cible, par FK MoveIt.

L'IK echoue souvent sur des poses 6D avec 5 axes ; la planification en espace articulaire, elle,
fonctionne. On balaye donc l'espace articulaire, on garde les k meilleures configurations et on les
donne a planifier a MoveIt.
"""
import itertools
import sys

import numpy as np
import rclpy
from moveit_msgs.srv import GetPositionFK
from rclpy.node import Node
from sensor_msgs.msg import JointState

CIBLE = np.array([float(v) for v in sys.argv[1:4]]) if len(sys.argv) >= 4 else np.array([0.36, 0.0, 0.30])

rclpy.init()
n = Node("cherche_pose")
cli = n.create_client(GetPositionFK, "/compute_fk")
cli.wait_for_service(timeout_sec=20.0)

j2s = np.linspace(-1.4, 1.4, 15)
j3s = np.linspace(-1.4, 1.4, 15)
j4s = (-1.5708, -0.7854, 0.0, 0.7854, 1.5708)
resultats = []
for j2, j3, j4 in itertools.product(j2s, j3s, j4s):
    js = JointState()
    js.name = ["arm_joint1", "arm_joint2", "arm_joint3", "arm_joint4", "arm_joint5", "grip_joint"]
    js.position = [0.0, float(j2), float(j3), float(j4), 0.0, -1.54]
    req = GetPositionFK.Request()
    req.header.frame_id = "base_link"
    req.fk_link_names = ["arm_link5"]
    req.robot_state.joint_state = js
    fut = cli.call_async(req)
    rclpy.spin_until_future_complete(n, fut, timeout_sec=5.0)
    if not fut.done() or not fut.result().pose_stamped:
        continue
    p = fut.result().pose_stamped[0].pose.position
    d = float(np.linalg.norm(np.array([p.x, p.y, p.z]) - CIBLE))
    resultats.append((d, round(float(j2), 3), round(float(j3), 3), round(float(j4), 3),
                      round(p.x, 3), round(p.y, 3), round(p.z, 3)))

resultats.sort()
print(f"cible {CIBLE.tolist()} — {len(resultats)} configurations evaluees")
print("  dist   j2     j3     j4     -> x      y      z")
for d, j2, j3, j4, x, y, z in resultats[:8]:
    print(f"  {d:.3f}  {j2:+.2f}  {j3:+.2f}  {j4:+.2f}  -> {x:+.3f} {y:+.3f} {z:+.3f}")
n.destroy_node()
rclpy.try_shutdown()
