"""Affiche les champs de précondition de /director/state, sur le robot (domaine 28).

Le message est une `std_msgs/String` qui contient du JSON : `ros2 topic echo` l'affiche entouré de
guillemets YAML et tronqué, d'où ce petit lecteur qui parle directement à rclpy plutôt que de
découper du texte.

    export ROS_DOMAIN_ID=28
    python3 scripts/etat_directeur.py
"""

from __future__ import annotations

import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def main() -> int:
    rclpy.init()
    noeud = Node("lecteur_etat_directeur")
    recus: list[dict] = []
    noeud.create_subscription(String, "/director/state", lambda m: recus.append(json.loads(m.data)), 10)

    fin = time.monotonic() + 6.0
    while time.monotonic() < fin and not recus:
        rclpy.spin_once(noeud, timeout_sec=0.2)
    noeud.destroy_node()
    rclpy.try_shutdown()

    if not recus:
        print("/director/state muet : directeur arrete ou domaine different")
        return 1
    etat = recus[-1]
    for cle in ("state", "task_id", "skill", "safety", "safety_age_s", "arm_angles",
                "arm_age_s", "arm_folded", "published_at"):
        print(f"{cle:14s} = {etat.get(cle)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
