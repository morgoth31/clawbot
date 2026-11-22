"""Localisation : `ekf_node` (odom + IMU -> /odom), parametres du paquet installe."""
from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    parametres = PathJoinSubstitution(
        [FindPackageShare("clawbot_bringup"), "config", "ekf.yaml"])
    return LaunchDescription([
        Node(package="robot_localization", executable="ekf_node", name="ekf_filter_node",
             output="screen", parameters=[parametres],
             remappings=[("odometry/filtered", "odom")]),
    ])
