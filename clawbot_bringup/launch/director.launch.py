"""Directeur S1 : /director/command, planification, preconditions de bras."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="clawbot_director", executable="director_node", name="director",
             output="screen"),
    ])
