"""Modele geometrique : /robot_description, /tf_static, /tf.

Deux noeuds seulement, et une seule source sur /joint_states : `joint_state_publisher`
republie les positions du bras publiees par le controleur sur /arm/joint_states. Le
pilote ne declare plus d'editeur sur ce topic (P13, REQ-ARM-001).

L'URDF est lu dans l'installation du paquet, jamais dans le dossier source.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    chemin = os.path.join(get_package_share_directory("clawbot_bringup"), "urdf",
                          "clawbot_x3plus.urdf")
    with open(chemin, encoding="utf-8") as flux:
        description = flux.read()

    parametres = {"robot_description": ParameterValue(description, value_type=str)}
    return LaunchDescription([
        Node(package="robot_state_publisher", executable="robot_state_publisher",
             name="robot_state_publisher", output="screen", parameters=[parametres]),
        Node(package="joint_state_publisher", executable="joint_state_publisher",
             name="joint_state_publisher", output="screen",
             parameters=[dict(parametres, source_list=["/arm/joint_states"], rate=20.0)]),
    ])
