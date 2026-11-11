"""Lance Nav2 sur la carte que le catalogue de waypoints désigne, et sur aucune autre.

Le point de ce fichier est d'éviter la panne silencieuse la plus coûteuse du lot : un catalogue qui
parle d'une carte pendant que Nav2 charge l'autre. La carte n'est donc pas un argument oublié avec
une valeur par défaut, elle est lue dans `config/waypoints.yaml` — le même fichier que le directeur
utilise pour résoudre un nom de waypoint.

Lancement :
  ros2 launch /home/jetson/clawbot/launch/navigation.launch.py
  ros2 launch /home/jetson/clawbot/launch/navigation.launch.py carte:=autre_carte

`clawbot-slam` doit être arrêté : SLAM Toolbox en cartographie publie `map -> odom`, AMCL aussi.
Deux éditeurs pour une seule transformation, c'est le même défaut que deux éditeurs pour
`/cmd_vel`. L'unité systemd `clawbot-nav2.service` déclare ce conflit explicitement.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

RACINE = Path(__file__).resolve().parents[1]
CATALOGUE = RACINE / "config" / "waypoints.yaml"
PARAMS = RACINE / "config" / "nav2_clawbot.yaml"
DOSSIER_CARTES = RACINE / "maps"


def carte_du_catalogue() -> str:
    """Nom de la carte de référence, tel que le catalogue le déclare."""
    contenu = yaml.safe_load(CATALOGUE.read_text(encoding="utf-8")) or {}
    nom = contenu.get("carte")
    if not nom:
        raise RuntimeError(f"{CATALOGUE} ne déclare aucune carte : Nav2 ne peut pas démarrer")
    return str(nom)


def generate_launch_description() -> LaunchDescription:
    carte = LaunchConfiguration("carte")
    parametres = LaunchConfiguration("params_file")
    bringup = os.path.join(get_package_share_directory("nav2_bringup"), "launch",
                           "bringup_launch.py")

    return LaunchDescription([
        # `autostart:=true` : les gestionnaires de cycle de vie activent les nœuds dès qu'ils
        # sont prêts. Un nœud non activé ne publie pas de costmap et le premier goal échoue.
        DeclareLaunchArgument(
            "carte", default_value=carte_du_catalogue(),
            description="Nom de la carte, sans extension, dans maps/"),
        DeclareLaunchArgument(
            "params_file", default_value=str(PARAMS),
            description="Paramètres Nav2 (cadres, vitesses, tolérances)"),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(bringup),
            launch_arguments={
                # slam:=False -> carte statique (map_server) + AMCL, et non SLAM Toolbox en ligne
                "slam": "False",
                "map": [DOSSIER_CARTES.as_posix(), "/", carte, ".yaml"],
                "params_file": parametres,
                "use_sim_time": "false",
                "autostart": "true",
            }.items()),
    ])
