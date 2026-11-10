#!/usr/bin/env python3
"""Chaine complete MoveIt -> controleur -> /servo_ctrl, sur un domaine isole.

    ROS_DOMAIN_ID=99 python3 tools/execute_demo.py [ready|demo]

Le script publie un /joint_states de reference (le domaine 99 n'a pas de
robot_state_publisher), demande a move_group de planifier *et executer* le groupe `arm`,
puis resume ce qui est reellement parti sur /servo_ctrl.

Sur le domaine 99, rien n'ecoute /servo_ctrl : le robot ne bouge pas. C'est un test de
chaine logicielle, pas un essai materiel.
"""

import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import Constraints, JointConstraint, PlanningOptions
from sensor_msgs.msg import JointState
from std_msgs.msg import Int32MultiArray

JOINTS = ['arm_joint1', 'arm_joint2', 'arm_joint3', 'arm_joint4', 'arm_joint5']
ALL_JOINTS = JOINTS + ['grip_joint', 'rlink_joint2', 'rlink_joint3',
                       'llink_joint1', 'llink_joint2', 'llink_joint3']
STATES = {
    'home': [0.0, 0.0, 0.0, 0.0, 0.0],
    'ready': [0.0, 0.5, 0.5, 0.0, 0.0],
    'demo': [0.3, 0.6, 0.2, -0.4, 0.5],
}


def main(argv):
    target = argv[1] if len(argv) > 1 else 'ready'
    positions = STATES[target]

    rclpy.init()
    node = Node('execute_demo')
    states = JointState()
    states.name = ALL_JOINTS
    states.position = [0.0] * len(ALL_JOINTS)
    states_pub = node.create_publisher(JointState, '/joint_states', 10)
    servos = []
    arm_states = []
    node.create_subscription(Int32MultiArray, '/servo_ctrl',
                             lambda m: servos.append((time.time(), list(m.data))), 100)
    node.create_subscription(JointState, '/arm/joint_states',
                             lambda m: arm_states.append(dict(zip(m.name, m.position))), 100)

    def publish_states():
        states.header.stamp = node.get_clock().now().to_msg()
        states_pub.publish(states)

    node.create_timer(0.05, publish_states)

    client = ActionClient(node, MoveGroup, '/move_action')
    if not client.wait_for_server(timeout_sec=15.0):
        print('ECHEC : /move_action absent — move_group n est pas lance sur ce domaine')
        return 1

    goal = MoveGroup.Goal()
    request = goal.request
    request.group_name = 'arm'
    request.num_planning_attempts = 5
    request.allowed_planning_time = 5.0
    request.max_velocity_scaling_factor = 0.5
    request.max_acceleration_scaling_factor = 0.5
    constraints = Constraints()
    for name, value in zip(JOINTS, positions):
        joint = JointConstraint()
        joint.joint_name = name
        joint.position = float(value)
        joint.tolerance_above = 0.05
        joint.tolerance_below = 0.05
        joint.weight = 1.0
        constraints.joint_constraints.append(joint)
    request.goal_constraints.append(constraints)
    goal.planning_options = PlanningOptions()
    goal.planning_options.plan_only = False

    send = client.send_goal_async(goal)
    deadline = time.time() + 20.0
    while not send.done() and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    handle = send.result()
    if not handle.accepted:
        print('ECHEC : objectif refuse par move_group')
        return 1

    result_future = handle.get_result_async()
    deadline = time.time() + 60.0
    while not result_future.done() and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    if not result_future.done():
        print('ECHEC : pas de resultat en 60 s')
        return 1

    result = result_future.result().result
    print(f'etat vise        : {target} {positions}')
    print(f'error_code MoveIt: {result.error_code.val} (1 = SUCCESS)')
    print(f'consignes servo  : {len(servos)}')
    if servos:
        par_servo = {}
        for _, data in servos:
            par_servo[data[0]] = data[1]
        print('derniers angles  : ' + ', '.join(
            f'servo{ident}={valeur}°' for ident, valeur in sorted(par_servo.items())))
    print(f'/arm/joint_states: {len(arm_states)} messages')
    if arm_states:
        print('derniere consigne: ' + ', '.join(
            f'{name}={arm_states[-1][name]:+.3f}' for name in JOINTS))
        ecart_max = max(abs(arm_states[-1][name] - value)
                        for name, value in zip(JOINTS, positions))
        print(f'ecart max        : {ecart_max:.4f} rad (tolerance 0,05)')
    node.destroy_node()
    rclpy.shutdown()
    return 0 if result.error_code.val == 1 and servos else 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
