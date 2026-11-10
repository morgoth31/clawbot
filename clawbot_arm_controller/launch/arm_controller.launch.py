#!/usr/bin/env python3
"""Lance le serveur d'action du bras (consignes servo, sans MoveIt).

    ros2 launch clawbot_arm_controller arm_controller.launch.py

Les correspondances articulation -> servo viennent de config/arm_controller.yaml
(installe avec le paquet). Pour les surcharger sans recompiler :

    ros2 launch clawbot_arm_controller arm_controller.launch.py \
        params_file:=/chemin/vers/mon_arm_controller.yaml
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    default_params = PathJoinSubstitution(
        [FindPackageShare('clawbot_arm_controller'), 'config', 'arm_controller.yaml'])

    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=default_params),
        Node(
            package='clawbot_arm_controller',
            executable='arm_trajectory_server',
            name='arm_trajectory_server',
            output='screen',
            parameters=[LaunchConfiguration('params_file')],
        ),
    ])
