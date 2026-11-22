"""Camera du poignet : v4l2_camera, 640x480, 15 Hz, cadre optique du poignet."""
from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    info = PathJoinSubstitution(
        [FindPackageShare("clawbot_bringup"), "config", "wrist_camera_info.yaml"])
    return LaunchDescription([
        Node(package="v4l2_camera", executable="v4l2_camera_node", name="camera",
             namespace="wrist_camera", output="screen",
             parameters=[{
                 "video_device": "/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera-video-index0",
                 "image_size": [640, 480],
                 "time_per_frame": [1, 15],
                 "pixel_format": "YUYV",
                 "output_encoding": "yuv422_yuy2",
                 "camera_frame_id": "wrist_camera_optical_frame",
                 "brightness": 0,
                 "gain": 0,
                 "camera_info_url": ["file://", info],
             }]),
    ])
