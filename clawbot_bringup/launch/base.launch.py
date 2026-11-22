"""Pilote de la base : `driver_node` (port serie du MCU, /cmd_vel_safe -> trames)."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="clawbot_base_driver", executable="driver_node", name="driver_node",
             output="screen"),
    ])
