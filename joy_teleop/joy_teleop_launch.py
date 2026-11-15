"""
Clawbot Joy Teleop Launch — Pro Controller Nintendo (Bluetooth ou USB-C)
──────────────────────────────────────────────────────────────────────────────
Deux processus :
  js_joy_source        → lit /dev/input/jsN et publie /joy (sensor_msgs/Joy)
  clawbot_joy_teleop   → /joy → /cmd_vel + /servo_ctrl

Pourquoi pas le paquet `joy` : il passe par SDL, qui énumère les deux nœuds
d'entrée du pad (le pad et son IMU) avec le même nom et un index instable —
après une reconnexion Bluetooth, l'index 0 désignait l'IMU et /joy sortait sans
aucun bouton, sans erreur. js_joy_source choisit le nœud par son nom de
périphérique et écarte les capteurs inertiels.

Usage:
  ROS_DOMAIN_ID=28 ros2 launch /home/jetson/clawbot/joy_teleop/joy_teleop_launch.py
  ROS_DOMAIN_ID=28 ros2 launch .../joy_teleop_launch.py arm_step:=5.0 linear_scale:=0.03
  ROS_DOMAIN_ID=28 ros2 launch .../joy_teleop_launch.py device_path:=/dev/input/js0
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    ros_domain = os.getenv("ROS_DOMAIN_ID", "28")

    declare_args = [
        DeclareLaunchArgument("device_path",    default_value="auto",
                              description="Nœud /dev/input/jsN forcé (auto = détection, IMU exclu)"),
        DeclareLaunchArgument("rate",           default_value="20.0",
                              description="Cadence de publication de /joy (Hz)"),
        DeclareLaunchArgument("deadzone",       default_value="0.05",
                              description="Zone morte appliquée aux axes"),
        DeclareLaunchArgument("linear_scale",   default_value="0.06",
                              description="Vitesse max m/s (plafond matériel 0.5)"),
        DeclareLaunchArgument("angular_scale",  default_value="0.25",
                              description="Rotation max rad/s (plafond matériel 1.5)"),
        DeclareLaunchArgument("arm_step",       default_value="3.0",
                              description="Degrés par tick bras"),
        DeclareLaunchArgument("deadman_button", default_value="-1",
                              description="Index bouton deadman (6 = ZR, -1 = désactivé)"),
        DeclareLaunchArgument("deadband",       default_value="0.08",
                              description="Seuil stick mort dans le nœud teleop"),
        DeclareLaunchArgument("manette_config", default_value="/home/jetson/clawbot/config/manette.yaml",
                              description="YAML produit par joy_teleop/calibration.py"),
    ]

    # js_joy_source — /dev/input/jsN → /joy (sans SDL, IMU écarté par nom)
    source = ExecuteProcess(
        cmd=[
            "python3",
            "/home/jetson/clawbot/joy_teleop/js_joy_source.py",
            "--ros-args",
            "-p", ["device_path:=", LaunchConfiguration("device_path")],
            "-p", ["rate:=",        LaunchConfiguration("rate")],
            "-p", ["deadzone:=",    LaunchConfiguration("deadzone")],
        ],
        additional_env={
            "ROS_DOMAIN_ID":    ros_domain,
            "PYTHONUNBUFFERED": "1",
        },
        output="screen",
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
            "-p", ["deadband:=",       LaunchConfiguration("deadband")],
            "-p", ["manette_config:=", LaunchConfiguration("manette_config")],
        ],
        additional_env={
            "ROS_DOMAIN_ID":    ros_domain,
            "PYTHONUNBUFFERED": "1",
        },
        output="screen",
    )

    return LaunchDescription([*declare_args, source, teleop_node])
