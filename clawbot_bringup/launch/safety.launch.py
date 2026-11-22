"""Arbitre de surete : seul editeur de /cmd_vel_safe.

Le fichier de parametres vient du paquet `clawbot_safety` installe ; il ne contient plus
d'entree `legacy` /cmd_vel depuis P14 (REQ-OPS-044).
"""
from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    parametres = PathJoinSubstitution(
        [FindPackageShare("clawbot_safety"), "config", "arbitrator.yaml"])
    return LaunchDescription([
        Node(package="clawbot_safety", executable="arbitrator", name="safety_arbitrator",
             output="screen", parameters=[parametres]),
    ])
