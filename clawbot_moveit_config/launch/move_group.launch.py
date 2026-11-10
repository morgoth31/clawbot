#!/usr/bin/env python3
"""Lance move_group pour le Clawbot X3 Plus.

    ros2 launch clawbot_moveit_config move_group.launch.py

Pre-requis, sur le domaine 28 :
  - clawbot-description.service : publie /robot_description et /tf ;
  - clawbot-arm-controller.service : sert /arm_controller/... et /grip_controller/... ;
  - /joint_states alimente par robot_state_publisher (source_list /arm/joint_states).

Le noeud ne commande rien tant qu'aucune trajectoire n'est *executee* : planifier est sans
effet sur le materiel.
"""

import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

DEFAULT_URDF = os.environ.get('CLAWBOT_URDF', '/home/jetson/clawbot/urdf/clawbot_x3plus.urdf')


def _load(path):
    with open(path, encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def generate_launch_description():
    share = get_package_share_directory('clawbot_moveit_config')

    with open(DEFAULT_URDF, encoding='utf-8') as handle:
        robot_description = handle.read()
    with open(os.path.join(share, 'config', 'clawbot_x3plus.srdf'), encoding='utf-8') as handle:
        semantic = handle.read()

    kinematics = _load(os.path.join(share, 'config', 'kinematics.yaml'))
    limits = _load(os.path.join(share, 'config', 'joint_limits.yaml'))
    ompl = _load(os.path.join(share, 'config', 'ompl_planning.yaml'))
    controllers = _load(os.path.join(share, 'config', 'moveit_controllers.yaml'))

    parameters = [{
        'robot_description': robot_description,
        'robot_description_semantic': semantic,
        'robot_description_kinematics': kinematics,
        'robot_description_planning': {'joint_limits': limits['joint_limits']},
        'default_planning_pipeline': 'ompl',
        'planning_pipelines': ['ompl'],
        'ompl': ompl,
        'moveit_controller_manager':
            'moveit_simple_controller_manager/MoveItSimpleControllerManager',
        'moveit_simple_controller_manager': controllers['moveit_simple_controller_manager'],
        'trajectory_execution': {
            'allowed_execution_duration_scaling': 1.2,
            'allowed_goal_duration_margin': 0.5,
            'allowed_start_tolerance': 0.05,
        },
        'use_sim_time': False,
        'publish_planning_scene': True,
        'publish_geometry_updates': True,
        'publish_state_updates': True,
        'publish_transforms_updates': True,
    }]

    return LaunchDescription([
        Node(
            package='moveit_ros_move_group',
            executable='move_group',
            name='move_group',
            output='screen',
            parameters=parameters,
        ),
    ])
