#!/usr/bin/env python3
"""Demande a MoveIt si une configuration est valide (collision) — sans bouger.

    ROS_DOMAIN_ID=28 python3 tools/check_state.py --servos 76 156 54 0 0

Les angles sont donnes en degres servo (l'axe 4 est optionnel, `0` = milieu de course).
La conversion utilise la convention du controleur : q = (angle - 90) / 57,2958.

Sortie : `valid` / `collision`, avec la liste des paires en collision.
"""

import argparse
import math
import sys
import time

import rclpy
from rclpy.node import Node

from moveit_msgs.msg import RobotState
from moveit_msgs.srv import GetStateValidity
from sensor_msgs.msg import JointState

JOINTS = ['arm_joint1', 'arm_joint2', 'arm_joint3', 'arm_joint4', 'arm_joint5']
RAD_PER_DEG = math.pi / 180.0
ZERO_DEG = 90.0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validation de configuration sans mouvement')
    parser.add_argument('--servos', nargs=5, type=float, required=True,
                        metavar=('S1', 'S2', 'S3', 'S4', 'S5'),
                        help='angles servo en degres pour arm_joint1..5')
    parser.add_argument('--group', default='arm')
    args = parser.parse_args(argv)

    positions = [(angle - ZERO_DEG) * RAD_PER_DEG for angle in args.servos]

    rclpy.init()
    node = Node('check_state')
    client = node.create_client(GetStateValidity, '/check_state_validity')
    if not client.wait_for_service(timeout_sec=15.0):
        print('ECHEC : /check_state_validity absent — move_group ne tourne pas')
        return 1

    etat = JointState()
    etat.name = list(JOINTS)
    etat.position = positions

    requete = GetStateValidity.Request()
    requete.group_name = args.group
    requete.robot_state = RobotState()
    requete.robot_state.joint_state = etat
    requete.robot_state.is_diff = False

    future = client.call_async(requete)
    deadline = time.time() + 15.0
    while not future.done() and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if not future.done():
        print('ECHEC : pas de reponse du service')
        return 1

    reponse = future.result()
    verdict = 'valide' if reponse.valid else 'EN COLLISION'
    print('angles servo   : ' + ', '.join(f'{a:.0f}' for a in args.servos))
    print('positions (rad): ' + ', '.join(f'{q:+.4f}' for q in positions))
    print(f'verdict        : {verdict} (group {args.group})')
    for contact in reponse.contacts:
        print(f'  contact : {contact.contact_body_1} <-> {contact.contact_body_2}')
    node.destroy_node()
    rclpy.shutdown()
    return 0 if reponse.valid else 2


if __name__ == '__main__':
    sys.exit(main())
