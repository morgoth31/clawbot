"""Executif de mission : /clawbot/execute_mission, budgets, journal JSONL."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="clawbot_executive", executable="mission_executive",
             name="mission_executive", output="screen"),
    ])
