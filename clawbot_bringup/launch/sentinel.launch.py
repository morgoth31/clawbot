"""Sentinelle : surveillance du journal de sante `/clawbot/health` (P14).

Sa sonde de flux est retiree : `health_monitor` est le seul proprietaire de la mesure,
la sentinelle lit son verdict au lieu de recalculer le sien.
"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="clawbot_sentinel", executable="sentinel", name="sentinel",
             output="screen"),
    ])
