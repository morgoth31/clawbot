"""Nav2 sur la carte que le catalogue de waypoints designe, et sur aucune autre.

Repris de `launch/navigation.launch.py` : la carte n'est pas un argument oublie avec une
valeur par defaut, elle est lue dans `config/waypoints.yaml` — le meme fichier que le
directeur utilise pour resoudre un nom de waypoint. Les chemins viennent de
l'installation du paquet, plus du dossier source.

`clawbot-slam` doit etre arrete : SLAM Toolbox en cartographie publie `map -> odom`, AMCL
aussi.
"""
from __future__ import annotations

import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

PARTAGE = get_package_share_directory("clawbot_bringup")
CATALOGUE = os.path.join(PARTAGE, "config", "waypoints.yaml")
PARAMS = os.path.join(PARTAGE, "config", "nav2_clawbot.yaml")
CARTES = os.path.join(PARTAGE, "maps")


def carte_du_catalogue() -> str:
    with open(CATALOGUE, encoding="utf-8") as flux:
        contenu = yaml.safe_load(flux) or {}
    nom = contenu.get("carte")
    if not nom:
        raise RuntimeError(f"{CATALOGUE} ne declare aucune carte : Nav2 ne peut pas demarrer")
    return str(nom)


def generate_launch_description() -> LaunchDescription:
    bringup = os.path.join(get_package_share_directory("nav2_bringup"), "launch",
                           "bringup_launch.py")
    return LaunchDescription([
        DeclareLaunchArgument("carte", default_value=carte_du_catalogue(),
                              description="Nom de la carte, sans extension, dans maps/"),
        DeclareLaunchArgument("params_file", default_value=PARAMS,
                              description="Parametres Nav2"),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(bringup),
            launch_arguments={
                "slam": "False",
                "map": [CARTES, "/", LaunchConfiguration("carte"), ".yaml"],
                "params_file": LaunchConfiguration("params_file"),
                "use_sim_time": "false",
                "autostart": "true",
            }.items()),
    ])
