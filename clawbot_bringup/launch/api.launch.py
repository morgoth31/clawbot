"""API HTTP 8000 : passerelle outillee vers l'executif (P14, REQ-OPS-043).

Le binaire C++ est celui du paquet installe. Ses routes de mouvement appellent
`/clawbot/execute_skill` / `/clawbot/execute_mission` ; l'URL du service materiel reste
utile pour les outils qui ne bougent pas le robot (capture, servo, batterie).
"""
import os

from ament_index_python.packages import get_package_prefix
from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    binaire = os.path.join(get_package_prefix("ros2_llm_bridge_cpp"), "lib",
                           "ros2_llm_bridge_cpp", "api_server")
    return LaunchDescription([
        ExecuteProcess(
            cmd=[binaire], name="llm_bridge", output="screen",
            additional_env={
                "HARDWARE_SERVICE_URL": "http://localhost:8001",
                "YOLO_SERVICE_URL": "http://localhost:8003",
                "BRIDGE_PORT": "8000",
            }),
    ])
