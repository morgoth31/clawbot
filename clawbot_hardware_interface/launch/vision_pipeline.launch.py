from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    usb_cam_node = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='usb_cam',
        parameters=[{
            'video_device': '/dev/video0',
            'framerate': 15.0,
            'image_width': 640,
            'image_height': 480,
            'pixel_format': 'yuyv',
            'camera_frame_id': 'camera_color_optical_frame',
        }],
        remappings=[
            ('image_raw', 'camera/image_raw'),
            ('camera_info', 'camera/camera_info'),
        ],
        output='screen'
    )

    # Static TF claw_link -> camera_color_optical_frame
    static_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        arguments=["0", "0", "0", "0", "0", "0", "claw_link", "camera_color_optical_frame"]
    )

    return LaunchDescription([
        usb_cam_node,
        static_tf
    ])
