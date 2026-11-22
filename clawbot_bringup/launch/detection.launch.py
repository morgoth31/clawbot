"""Detection d'objets : `yolo_node.noeud` dans le venv GPU (facade HTTP 8003).

Le noeud tourne dans `/home/jetson/yolov5_env`, pas dans le python systeme : c'est une
contrainte du moteur TensorRT installe la, et la seule exception au lancement par
`Node(package=…)` de ce paquet.
"""
from launch import LaunchDescription
from launch.actions import ExecuteProcess

PYTHON_VENV = "/home/jetson/yolov5_env/bin/python3"


def generate_launch_description():
    return LaunchDescription([
        ExecuteProcess(
            cmd=[PYTHON_VENV, "-m", "yolo_node.noeud", "--ros-args",
                 "-p", "http_port:=8003", "-p", "max_rate_hz:=5.0"],
            name="yolo_node", output="screen"),
    ])
