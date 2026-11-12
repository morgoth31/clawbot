import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node as NodeAction
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    port_arg = DeclareLaunchArgument('port', default_value='8000')
    hw_url_arg = DeclareLaunchArgument('hw_url', default_value='http://localhost:8001')

    return LaunchDescription([
        port_arg,
        hw_url_arg,
        NodeAction(
            package='ros2_llm_bridge_cpp',
            executable='api_server',
            name='llm_bridge_node',
            parameters=[],
            additional_env={
                'BRIDGE_PORT': LaunchConfiguration('port'),
                'HARDWARE_SERVICE_URL': LaunchConfiguration('hw_url'),
                'ROS_DOMAIN_ID': '28',
            },
            output='screen',
        ),
    ])