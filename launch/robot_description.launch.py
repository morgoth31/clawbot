#!/usr/bin/env python3
"""Charge le modele geometrique du Clawbot X3 Plus sur le robot (domaine 28).

Publie /robot_description, /tf_static et /tf. Ne commande rien : aucun actionneur
n'est pilote par ce noeud, il ne fait que decrire le robot.

- robot_state_publisher : la description (bras 5 axes, pince, cameras, laser, roues)
- joint_state_publisher  : positions par defaut tant que le pilote du bras ne publie
                           pas /joint_states ; a retirer le jour ou il le fera
Le pilote YDLIDAR est configure pour publier frame_id="laser_link" (params
config/ydlidar_x3plus.yaml), donc aucun alias de frame n'est necessaire.
"""
import os

from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

URDF = os.environ.get('CLAWBOT_URDF', '/home/jetson/clawbot/urdf/clawbot_x3plus.urdf')


def generate_launch_description():
    with open(URDF, 'r', encoding='utf-8') as fh:
        description = fh.read()

    rsp = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': ParameterValue(description, value_type=str)}],
    )

    # la description est passee en parametre : joint_state_publisher n'attend pas
    # le topic /robot_description (qui reste en transient_local cote RSP)
    jsp = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
        parameters=[{'robot_description': ParameterValue(description, value_type=str)}],
    )

    return LaunchDescription([rsp, jsp])
