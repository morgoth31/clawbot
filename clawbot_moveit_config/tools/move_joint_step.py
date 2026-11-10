#!/usr/bin/env python3
"""Deplace UNE articulation du bras d'un petit increment via MoveIt, tout le reste tenu.

    ROS_DOMAIN_ID=28 python3 tools/move_joint_step.py --joint arm_joint1 --delta-deg -5

Le script lit l'etat courant sur /joint_states, construit un objectif ou seule
l'articulation visee bouge (les autres sont contraintes a leur valeur courante avec une
tolerance serree), puis demande a move_group de planifier ET executer.

Garde-fous : delta limite a 10°, tolerance des axes tenus a 0,005 rad, refus si l'etat
courant est indisponible ou si l'articulation n'appartient pas au groupe `arm`.
"""

import argparse
import math
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import Constraints, JointConstraint, PlanningOptions
from sensor_msgs.msg import JointState

JOINTS = ['arm_joint1', 'arm_joint2', 'arm_joint3', 'arm_joint4', 'arm_joint5']
MAX_DELTA_DEG = 10.0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Pas articulaire unique via MoveIt')
    parser.add_argument('--joint', required=True, choices=JOINTS)
    parser.add_argument('--delta-deg', type=float, required=True)
    parser.add_argument('--vel-scale', type=float, default=0.2)
    parser.add_argument('--plan-only', action='store_true')
    args = parser.parse_args(argv)

    if abs(args.delta_deg) > MAX_DELTA_DEG:
        print(f'REFUS : |delta| {abs(args.delta_deg):.1f} deg > {MAX_DELTA_DEG} deg')
        return 2

    rclpy.init()
    node = Node('move_joint_step')
    etats = {}
    node.create_subscription(JointState, '/joint_states',
                             lambda m: etats.update(dict(zip(m.name, m.position))), 20)

    deadline = time.time() + 10.0
    while time.time() < deadline and not all(j in etats for j in JOINTS):
        rclpy.spin_once(node, timeout_sec=0.1)
    manquants = [j for j in JOINTS if j not in etats]
    if manquants:
        print(f'ECHEC : articulation(s) absente(s) de /joint_states : {manquants}')
        return 1

    courant = {j: etats[j] for j in JOINTS}
    delta = math.radians(args.delta_deg)
    cible = dict(courant)
    cible[args.joint] = courant[args.joint] + delta

    print('etat courant  : ' + ', '.join(f'{j}={courant[j]:+.4f}' for j in JOINTS))
    print(f'objectif      : {args.joint} {courant[args.joint]:+.4f} -> '
          f'{cible[args.joint]:+.4f} rad ({args.delta_deg:+.1f} deg)')

    client = ActionClient(node, MoveGroup, '/move_action')
    if not client.wait_for_server(timeout_sec=15.0):
        print('ECHEC : /move_action absent — move_group ne tourne pas sur ce domaine')
        return 1

    goal = MoveGroup.Goal()
    request = goal.request
    request.group_name = 'arm'
    request.num_planning_attempts = 10
    request.allowed_planning_time = 5.0
    request.max_velocity_scaling_factor = args.vel_scale
    request.max_acceleration_scaling_factor = args.vel_scale

    constraints = Constraints()
    for joint in JOINTS:
        item = JointConstraint()
        item.joint_name = joint
        item.position = float(cible[joint])
        tolerance = 0.02 if joint == args.joint else 0.005
        item.tolerance_above = tolerance
        item.tolerance_below = tolerance
        item.weight = 1.0
        constraints.joint_constraints.append(item)
    request.goal_constraints.append(constraints)
    goal.planning_options = PlanningOptions()
    goal.planning_options.plan_only = bool(args.plan_only)

    send = client.send_goal_async(goal)
    deadline = time.time() + 20.0
    while not send.done() and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    handle = send.result()
    if handle is None or not handle.accepted:
        print('ECHEC : objectif refuse par move_group')
        return 1

    result_future = handle.get_result_async()
    deadline = time.time() + 60.0
    while not result_future.done() and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    if not result_future.done():
        print('ECHEC : aucun resultat en 60 s')
        return 1

    result = result_future.result().result
    erreur = 0 if result.error_code.val == 1 else result.error_code.val
    print(f'error_code    : {result.error_code.val} (1 = SUCCESS)')
    print(f'planifie      : {len(result.planned_trajectory.joint_trajectory.points)} points, '
          f'{result.planning_time:.2f} s de calcul')
    node.destroy_node()
    rclpy.shutdown()
    return erreur


if __name__ == '__main__':
    sys.exit(main())
