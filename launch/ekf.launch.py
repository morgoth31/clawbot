"""Lance le filtre EKF qui publie /odom et la TF odom -> base_link."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = LaunchConfiguration("config")
    return LaunchDescription([
        DeclareLaunchArgument(
            "config",
            default_value=os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "ekf.yaml"),
            description="Fichier de paramètres du filtre EKF",
        ),
        Node(
            package="robot_localization",
            executable="ekf_node",
            name="ekf_filter_node",
            output="screen",
            parameters=[config],
            # robot_localization publie `odometry/filtered` par défaut : le contrat du robot
            # est `/odom` (consommé par Nav2, SLAM et le bridge MCP).
            remappings=[("odometry/filtered", "odom")],
        ),
    ])
