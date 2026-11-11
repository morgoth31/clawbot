"""Planifie un mouvement du bras avec MoveIt 2 et, sur demande, l'execute.

    python3 moveit_plan.py ready            # planifie vers l'etat nomme `ready` du SRDF
    python3 moveit_plan.py ready --executer # planifie puis execute via MoveGroup
    python3 moveit_plan.py --pose 0.30 0.00 0.15   # planifie vers une position (orientation libre)

Sans `--executer`, rien ne bouge : planifier n'a aucun effet sur le materiel.
"""
from __future__ import annotations

import sys
import time

import rclpy
from geometry_msgs.msg import Pose
from moveit_msgs.msg import (Constraints, JointConstraint, MoveItErrorCodes,
                             OrientationConstraint)
from moveit_msgs.srv import GetMotionPlan
from rclpy.action import ActionClient
from rclpy.node import Node
from moveit_msgs.action import MoveGroup

CODES = {k: v for k, v in vars(MoveItErrorCodes).items()
         if isinstance(v, int) and not k.startswith("_")}


def nom_code(valeur: int) -> str:
    for nom, v in CODES.items():
        if v == valeur:
            return nom
    return str(valeur)


def main() -> int:
    args = sys.argv[1:]
    executer = "--executer" in args or "--execute" in args
    args = [a for a in args if a not in ("--executer", "--execute")]

    rclpy.init()
    n = Node("moveit_plan")
    cli = n.create_client(GetMotionPlan, "/plan_kinematic_path")
    if not cli.wait_for_service(timeout_sec=15.0):
        print("ECHEC : /plan_kinematic_path absent")
        return 2

    req = GetMotionPlan.Request()
    mpr = req.motion_plan_request
    mpr.group_name = "arm"
    mpr.num_planning_attempts = 3
    mpr.allowed_planning_time = 5.0
    mpr.max_velocity_scaling_factor = 0.4
    mpr.max_acceleration_scaling_factor = 0.4

    if args and args[0] == "--pose":
        x, y, z = (float(v) for v in args[1:4])
        pose = Pose()
        pose.position.x, pose.position.y, pose.position.z = x, y, z
        pose.orientation.w = 1.0
        c = Constraints()
        oc = OrientationConstraint()
        oc.header.frame_id = "base_link"
        oc.link_name = "arm_link5"
        oc.orientation.w = 1.0
        oc.absolute_x_axis_tolerance = 3.14
        oc.absolute_y_axis_tolerance = 3.14
        oc.absolute_z_axis_tolerance = 3.14
        oc.weight = 1.0
        c.orientation_constraints.append(oc)
        from moveit_msgs.msg import PositionConstraint
        from shape_msgs.msg import SolidPrimitive
        pc = PositionConstraint()
        pc.header.frame_id = "base_link"
        pc.link_name = "arm_link5"
        s = SolidPrimitive()
        s.type = SolidPrimitive.SPHERE
        s.dimensions = [0.01]
        pc.constraint_region.primitives.append(s)
        pc.constraint_region.primitive_poses.append(pose)
        pc.weight = 1.0
        c.position_constraints.append(pc)
        mpr.goal_constraints.append(c)
        print(f"cible : position ({x:+.3f}, {y:+.3f}, {z:+.3f}) dans base_link, orientation libre")
    else:
        # Les contraintes nommees (`Constraints.name`) ne se resolvent pas via ce service : on
        # envoie des contraintes articulaires explicites, ce qui verifie du meme coup les noms
        # et les bornes des articulations.
        ETATS = {"home": [0.0, 0.0, 0.0, 0.0, 0.0],
                 "ready": [0.0, 0.5, 0.5, 0.0, 0.0]}
        cible = args[0] if args else "ready"
        valeurs = ETATS.get(cible)
        if valeurs is None:
            valeurs = [float(v) for v in cible.split(",")]
        if len(valeurs) != 5:
            print(f"ECHEC : 5 angles attendus, recu {len(valeurs)}")
            return 2
        c = Constraints()
        for i, valeur in enumerate(valeurs, start=1):
            jc = JointConstraint()
            jc.joint_name = f"arm_joint{i}"
            jc.position = valeur
            jc.tolerance_above = 0.01
            jc.tolerance_below = 0.01
            jc.weight = 1.0
            c.joint_constraints.append(jc)
        mpr.goal_constraints.append(c)
        print(f"cible : arm_joint1..5 = {valeurs}")

    fut = cli.call_async(req)
    rclpy.spin_until_future_complete(n, fut, timeout_sec=40.0)
    if not fut.done():
        print("ECHEC : pas de reponse du planificateur")
        return 3
    rep = fut.result()
    code = rep.motion_plan_response.error_code.val
    print(f"planification : {nom_code(code)} ({code})")
    if code != 1:
        return 4
    traj = rep.motion_plan_response.trajectory.joint_trajectory
    pts = traj.points
    print(f"points de trajectoire : {len(pts)} sur {pts[-1].time_from_start.sec + pts[-1].time_from_start.nanosec/1e9:.1f} s")
    for i in (0, len(pts) // 2, len(pts) - 1):
        p = pts[i]
        angles = ", ".join(f"{a:+.2f}" for a in p.positions)
        t = p.time_from_start.sec + p.time_from_start.nanosec / 1e9
        print(f"  t={t:5.2f}s  [{angles}]")

    if not executer:
        print("(planification seule — rien n'a bouge ; ajouter --executer)")
        return 0

    client = ActionClient(n, MoveGroup, "/move_action")
    if not client.wait_for_server(timeout_sec=15.0):
        print("ECHEC : /move_action absent")
        return 5
    objectif = MoveGroup.Goal()
    objectif.request = mpr
    objectif.planning_options.plan_only = False
    objectif.planning_options.replan = False
    print("execution demandee…")
    envoi = client.send_goal_async(objectif)
    rclpy.spin_until_future_complete(n, envoi, timeout_sec=20.0)
    handle = envoi.result()
    if not handle.accepted:
        print("ECHEC : objectif refuse")
        return 6
    res = handle.get_result_async()
    rclpy.spin_until_future_complete(n, res, timeout_sec=60.0)
    if not res.done():
        print("ECHEC : execution sans reponse")
        return 7
    print(f"execution : {nom_code(res.result().result.error_code.val)}")
    time.sleep(1.0)
    n.destroy_node()
    rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
