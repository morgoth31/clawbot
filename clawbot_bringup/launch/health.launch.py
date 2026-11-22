"""Surveillance des flux : publie `/clawbot/health`, alerte sur flux perime."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="clawbot_health", executable="health_monitor", name="health_monitor",
             output="screen"),
    ])
