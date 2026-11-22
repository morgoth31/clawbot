"""Camera de profondeur Astra Pro : lancement vendor, conserve tel quel.

Le pilote vient de l'espace de travail vendor (`yahboomcar_ros2_ws/software/library_ws`) :
l'unite source cet overlay avant `ros2 launch`. Ce fichier ne fait que nommer le point
d'entree, pour que l'unite n'ait plus a connaitre le nom du lancement vendor.
"""
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import XmlLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    vendor = IncludeLaunchDescription(
        XmlLaunchDescriptionSource(PathJoinSubstitution(
            [FindPackageShare("astra_camera"), "launch", "astro_pro_plus.launch.xml"])))
    return LaunchDescription([vendor])
