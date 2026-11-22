"""Controleur de trajectoire du bras (action FollowJointTrajectory -> /servo_ctrl)."""
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    controleur = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution(
            [FindPackageShare("clawbot_arm_controller"), "launch",
             "arm_controller.launch.py"])))
    return LaunchDescription([controleur])
