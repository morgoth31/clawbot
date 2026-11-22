"""Lidar YDLIDAR TG30 : `/scan` a 10 Hz, `frame_id=laser_link`.

Le fichier de parametres est celui du paquet installe : sans lui, le pilote publie dans
le cadre par defaut et le scan ne s'accroche pas a l'URDF.
"""
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    parametres = PathJoinSubstitution(
        [FindPackageShare("clawbot_bringup"), "config", "ydlidar_x3plus.yaml"])
    pilote = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution(
            [FindPackageShare("ydlidar_ros2_driver"), "launch", "ydlidar_raw_launch.py"])),
        launch_arguments={"params_file": parametres}.items())
    return LaunchDescription([pilote])
