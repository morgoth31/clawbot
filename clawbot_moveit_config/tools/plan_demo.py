#!/usr/bin/env python3
"""Demande un plan a move_group (aucune execution) et resume la trajectoire.

    ROS_DOMAIN_ID=28 python3 tools/plan_demo.py [ready|home]

Le service /plan_kinematic_path ne fait que planifier : rien n'est envoye aux servos.
"""

import sys
import time

import rclpy
from rclpy.node import Node

from moveit_msgs.srv import GetMotionPlan
from moveit_msgs.msg import Constraints, JointConstraint, PositionConstraint
from moveit_msgs.msg import BoundingVolume
from shape_msgs.msg import SolidPrimitive
from geometry_msgs.msg import Pose

GROUP = 'arm'
JOINTS = ['arm_joint1', 'arm_joint2', 'arm_joint3', 'arm_joint4', 'arm_joint5']
STATES = {
    'home': [0.0, 0.0, 0.0, 0.0, 0.0],
    'ready': [0.0, 0.5, 0.5, 0.0, 0.0],
    'demo': [0.3, 0.6, 0.2, -0.4, 0.5],
}


def main(argv):
    target = argv[1] if len(argv) > 1 else 'ready'
    positions = STATES[target]

    rclpy.init()
    node = Node('plan_demo')
    client = node.create_client(GetMotionPlan, '/plan_kinematic_path')
    if not client.wait_for_service(timeout_sec=10.0):
        print('ECHEC : service /plan_kinematic_path absent')
        return 1

    request = GetMotionPlan.Request()
    plan_request = request.motion_plan_request
    plan_request.group_name = GROUP
    plan_request.num_planning_attempts = 5
    plan_request.allowed_planning_time = 5.0
    plan_request.max_velocity_scaling_factor = 0.5
    plan_request.max_acceleration_scaling_factor = 0.5
    plan_request.planner_id = 'RRTConnect'

    constraints = Constraints()
    for name, value in zip(JOINTS, positions):
        joint = JointConstraint()
        joint.joint_name = name
        joint.position = float(value)
        joint.tolerance_above = 0.05
        joint.tolerance_below = 0.05
        joint.weight = 1.0
        constraints.joint_constraints.append(joint)
    plan_request.goal_constraints.append(constraints)

    future = client.call_async(request)
    deadline = time.time() + 20.0
    while not future.done() and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if not future.done():
        print('ECHEC : pas de reponse du planificateur')
        return 1

    response = future.result()
    result = response.motion_plan_response
    print(f'etat vise      : {target} {positions}')
    print(f'error_code     : {result.error_code.val} (1 = SUCCESS)')
    trajectory = result.trajectory.joint_trajectory
    print(f'articulations  : {list(trajectory.joint_names)}')
    print(f'points         : {len(trajectory.points)}')
    if trajectory.points:
        last = trajectory.points[-1]
        print('position finale: '
              + ', '.join(f'{q:+.3f}' for q in last.positions))
        duration = last.time_from_start.sec + last.time_from_start.nanosec * 1e-9
        print(f'duree          : {duration:.2f} s')
        first = trajectory.points[0]
        print('position depart: '
              + ', '.join(f'{q:+.3f}' for q in first.positions))
    print(f'planification  : {result.planning_time:.3f} s')
    node.destroy_node()
    rclpy.shutdown()
    return 0 if result.error_code.val == 1 else 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
