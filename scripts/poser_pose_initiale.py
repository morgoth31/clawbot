"""Déclare à AMCL la pose de départ du robot, sur un waypoint du catalogue.

Pourquoi cet outil existe : AMCL ne devine pas où est le robot. `config/nav2_clawbot.yaml` suppose
le waypoint `ouest` au démarrage — c'est une hypothèse de mise en route, pas une mesure. Dès que
l'opérateur sait où le robot est réellement (il l'a posé, il l'a poussé), il le déclare ici, et la
localisation repart de cette vérité-là.

Usage, robot posé sur un waypoint nommé :

    source /opt/ros/humble/setup.bash && export ROS_DOMAIN_ID=28
    python3 scripts/poser_pose_initiale.py ouest

Ou avec une pose mesurée à la main, entre guillemets :

    python3 scripts/poser_pose_initiale.py "1.42,-0.35,0.0"

Le script refuse de tourner hors du domaine 28 : déclarer une pose à AMCL ne veut rien dire s'il
n'y a pas d'AMCL en face, et une faute de domaine donnerait l'illusion d'un succès.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

if os.environ.get("ROS_DOMAIN_ID") != "28":
    raise SystemExit(
        f"ROS_DOMAIN_ID={os.environ.get('ROS_DOMAIN_ID')} : ce script vise le robot, "
        "exportez ROS_DOMAIN_ID=28")

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "clawbot_director"))

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node

from clawbot_director import waypoints as catalogue_waypoints


def _pose_depuis_entree(entree: str, catalogue) -> tuple[float, float, float]:
    if "," in entree:
        morceaux = [m.strip() for m in entree.split(",")]
        if len(morceaux) != 3:
            raise SystemExit("pose attendue : x,y,yaw")
        return tuple(float(m) for m in morceaux)          # type: ignore[return-value]
    waypoint = catalogue.resoudre(entree)                 # lève si le nom est inconnu
    return waypoint.x, waypoint.y, waypoint.yaw


def main() -> int:
    analyseur = argparse.ArgumentParser(description="Pose initiale AMCL")
    analyseur.add_argument("position", help="nom de waypoint du catalogue, ou \"x,y,yaw\"")
    analyseur.add_argument("--delai", type=float, default=6.0,
                           help="secondes de republication (AMCL echantillonne)")
    arguments = analyseur.parse_known_args()[0]

    catalogue = catalogue_waypoints.charger()
    x, y, yaw = _pose_depuis_entree(arguments.position, catalogue)

    rclpy.init()
    noeud = Node("pose_initiale_amcl")
    publication = noeud.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
    message = PoseWithCovarianceStamped()
    message.header.frame_id = catalogue.frame
    message.pose.pose.position.x = x
    message.pose.pose.position.y = y
    message.pose.pose.orientation.z = math.sin(yaw / 2.0)
    message.pose.pose.orientation.w = math.cos(yaw / 2.0)
    # covariance franche : AMCL doit comprendre « je ne sais pas, cherche autour »
    message.pose.covariance[0] = 0.25
    message.pose.covariance[7] = 0.25
    message.pose.covariance[35] = 0.07

    try:
        fin = noeud.get_clock().now().nanoseconds / 1e9 + arguments.delai
        while noeud.get_clock().now().nanoseconds / 1e9 < fin:
            message.header.stamp = noeud.get_clock().now().to_msg()
            publication.publish(message)
            rclpy.spin_once(noeud, timeout_sec=0.2)
        noeud.get_logger().info(
            f"pose initiale publiee : ({x:.2f}, {y:.2f}, {yaw:.2f}) sur {catalogue.carte}")
    finally:
        noeud.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
