"""Planificateur MoveIt 2 (move_group) : planifie et execute les poses du bras."""
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    move_group = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution(
            [FindPackageShare("clawbot_moveit_config"), "launch", "move_group.launch.py"])))
    return LaunchDescription([move_group])
