"""Service materiel HTTP 8001 (capture, servo, buzzer, /motion).

Ce n'est pas un noeud ROS executable : c'est un service FastAPI qui cree son propre
noeud rclpy. Il est lance comme module du paquet, donc depuis l'installation.
"""
import sys

from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    return LaunchDescription([
        ExecuteProcess(cmd=[sys.executable, "-m", "clawbot_bringup.hardware_service"],
                       name="hardware_service", output="screen"),
    ])
