"""Serveur de skills : action /clawbot/execute_skill, un skill a la fois."""
from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    poses = PathJoinSubstitution(
        [FindPackageShare("clawbot_bringup"), "config", "arm_poses.yaml"])
    preconditions = PathJoinSubstitution(
        [FindPackageShare("clawbot_bringup"), "config", "preconditions.yaml"])
    return LaunchDescription([
        Node(package="clawbot_executive", executable="skill_server", name="skill_server",
             output="screen",
             parameters=[{"arm_poses": poses, "preconditions": preconditions}]),
    ])
