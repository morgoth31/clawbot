"""
Clawbot Joy Teleop Launch — Pro Controller / manette générique
──────────────────────────────────────────────────────────────
Détecte automatiquement la manette par nom (device_name) ou index.

Usage:
  ROS_DOMAIN_ID=28 ros2 launch /home/jetson/clawbot/joy_teleop/joy_teleop_launch.py
  ROS_DOMAIN_ID=28 ros2 launch /home/jetson/clawbot/joy_teleop/joy_teleop_launch.py \
    arm_step:=5.0 linear_scale:=0.05
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    ros_domain = os.getenv("ROS_DOMAIN_ID", "28")

    declare_args = [
        DeclareLaunchArgument("device_id",       default_value="0",     description="Index /dev/input/js? (0 = auto)"),
        DeclareLaunchArgument("linear_scale",    default_value="0.5",  description="Vitesse max m/s"),
        DeclareLaunchArgument("angular_scale",   default_value="1.5",  description="Rotation max rad/s"),
        DeclareLaunchArgument("arm_step",        default_value="3.0",   description="Degrés par tick bras"),
        DeclareLaunchArgument("deadman_button",  default_value="-1",    description="Index bouton deadman (8=ZR/BtnTR2, -1=always active)"),
        DeclareLaunchArgument("invert_ly",       default_value="true",  description="Inverser stick gauche Y"),
        DeclareLaunchArgument("invert_ry",       default_value="true",  description="Inverser stick droit Y"),
        DeclareLaunchArgument("deadband",        default_value="0.08",  description="Zone morte joystick"),
    ]

    # joy_node — détection automatique du premier joystick disponible
    joy_node = Node(
        package="joy",
        executable="joy_node",
        name="joy_node",
        output="screen",
        parameters=[{
            "device_id":       LaunchConfiguration("device_id"),
            "deadzone":        0.05,
            "autorepeat_rate": 20.0,   # 20Hz pour un mouvement fluide
            "coalesce_interval_ms": 4, # réduit la latence
        }],
    )

    # clawbot_joy_teleop — /joy → /cmd_vel + /servo_ctrl
    teleop_node = ExecuteProcess(
        cmd=[
            "python3",
            "/home/jetson/clawbot/joy_teleop/clawbot_joy_teleop.py",
            "--ros-args",
            "-p", ["linear_scale:=",   LaunchConfiguration("linear_scale")],
            "-p", ["angular_scale:=",  LaunchConfiguration("angular_scale")],
            "-p", ["arm_step:=",       LaunchConfiguration("arm_step")],
            "-p", ["deadman_button:=", LaunchConfiguration("deadman_button")],
            "-p", ["invert_ly:=",      LaunchConfiguration("invert_ly")],
            "-p", ["invert_ry:=",      LaunchConfiguration("invert_ry")],
            "-p", ["deadband:=",       LaunchConfiguration("deadband")],
        ],
        additional_env={
            "ROS_DOMAIN_ID":    ros_domain,
            "PYTHONUNBUFFERED": "1",
        },
        output="screen",
    )

    return LaunchDescription([*declare_args, joy_node, teleop_node])
