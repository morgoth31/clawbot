"""Gestionnaire de capacites : liste blanche d'unites, conflits, etats."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="clawbot_capabilities", executable="gestionnaire",
             name="capability_manager", output="screen"),
    ])
