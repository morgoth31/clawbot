"""Teleoperation manette : attente de l'appareil, puis `joy_teleop`.

Le script d'attente est conserve : il choisit le noeud d'entree du pad par son nom (les
index SDL ont permute apres une reconnexion Bluetooth, mesure du 2026-11-15). Le
transcrire en Python dans ce fichier serait une reecriture sans test, pour une unite qui
n'est pas demarree par defaut.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    script = os.path.join(get_package_share_directory("clawbot_bringup"), "scripts",
                          "joy_teleop_wait.sh")
    return LaunchDescription([
        ExecuteProcess(cmd=["/bin/bash", script], name="joy_teleop", output="screen"),
    ])
