"""Cartographie SLAM : `slam_toolbox` en mode mapping, /map pour la capacite `mapping`."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="slam_toolbox", executable="async_slam_toolbox_node",
             name="slam_toolbox", output="screen",
             parameters=[{
                 "base_frame": "base_link",
                 "odom_frame": "odom",
                 "map_frame": "map",
                 "scan_topic": "/scan",
                 "mode": "mapping",
                 "use_sim_time": False,
                 "resolution": 0.05,
                 "minimum_travel_distance": 0.2,
                 "minimum_travel_heading": 0.2,
                 "map_update_interval": 2.0,
             }]),
    ])
