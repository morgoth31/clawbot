"""
Clawbot SLAM Launch — Cartographer 2D, no odometry, no driver_node conflict.

Stack:
  TF1: base_footprint → base_link  (xyz: 0 0 0.0815  from URDF)
  TF2: base_link → laser           (xyz: 0.0435 5.26e-5 0.11 from URDF/4ROS config)
  YDLidar  → /scan  (frame: laser)
  Cartographer → /map, /submap_list, /tf (map→odom→base_footprint)
  OccupancyGrid publisher → /map (from cartographer submaps)

Run:
  ROS_DOMAIN_ID=28 ros2 launch /home/jetson/clawbot/slam_launch.py

Save map (when done):
  ros2 run nav2_map_server map_saver_cli -f /home/jetson/clawbot/maps/mymap \\
    --ros-args -p map_subscribe_transient_local:=true
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

NAV_PKG   = get_package_share_directory('yahboomcar_nav')
YDLIDAR_PKG = get_package_share_directory('ydlidar_ros2_driver')


def generate_launch_description():
    # ── Static TF: base_footprint → base_link (z=0.0815 from URDF) ────────────
    tf_footprint_to_base = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_footprint_base',
        arguments=['0', '0', '0.0815', '0', '0', '0',
                   'base_footprint', 'base_link'],
        output='screen',
    )

    # ── Static TF: base_link → laser (from URDF laser_joint + 4ROS config) ────
    tf_base_to_laser = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_base_laser',
        arguments=['0.0435', '0.0000526', '0.11', '0', '0', '0',
                   'base_link', 'laser'],
        output='screen',
    )

    # ── YDLidar driver ────────────────────────────────────────────────────────
    ydlidar = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(YDLIDAR_PKG, 'launch', 'ydlidar_raw_launch.py')
        )
    )

    # ── Cartographer 2D ───────────────────────────────────────────────────────
    cartographer = Node(
        package='cartographer_ros',
        executable='cartographer_node',
        name='cartographer_node',
        output='screen',
        parameters=[{'use_sim_time': False}],
        arguments=[
            '-configuration_directory', os.path.join(NAV_PKG, 'params'),
            '-configuration_basename', 'lds_2d.lua',
        ],
    )

    # ── Occupancy grid from Cartographer submaps → /map ───────────────────────
    occupancy_grid = Node(
        package='cartographer_ros',
        executable='cartographer_occupancy_grid_node',
        name='occupancy_grid_node',
        output='screen',
        parameters=[{'use_sim_time': False, 'resolution': 0.05, 'publish_period_sec': 1.0}],
    )

    return LaunchDescription([
        tf_footprint_to_base,
        tf_base_to_laser,
        ydlidar,
        cartographer,
        occupancy_grid,
    ])
