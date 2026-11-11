"""Nœud ROS du directeur : la logique pure de `director.py` branchée au graphe.

Le directeur décide quand un skill peut tourner, jamais ce que le robot doit faire. Ce nœud
ajoute ce que la logique pure ne peut pas voir : l'état de sécurité publié par l'arbitre sur
/safety/state. Règle unique et non négociable : dès que cet état sort de OK, la tâche en cours
est annulée, sans attendre le prochain point sûr — la sécurité prime sur la séquence.

/director/state publie l'état interrogeable (task_id, skill, étape) accompagné de la dernière
valeur de sécurité connue, pour que S2 et la supervision lisent la même chose.
"""

from __future__ import annotations

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .director import Director

SAFETY_OK = "OK"
STATE_PERIOD_S = 0.2   # 5 Hz : l'état est aussi republié tel quel, sans changement


class DirectorNode(Node):
    def __init__(self):
        super().__init__("director")
        self.director = Director()
        self.safety = "UNKNOWN"     # rien reçu tant que l'arbitre n'a pas parlé

        self.pub_state = self.create_publisher(String, "/director/state", 10)
        self.create_subscription(String, "/safety/state", self.on_safety, 10)
        self.create_timer(STATE_PERIOD_S, self.publish_state)
        self.publish_state()

    def on_safety(self, msg):
        etat = msg.data.strip().upper()
        self.safety = etat
        if etat != SAFETY_OK:
            resultat = self.director.cancel(reason="safety")
            if resultat.get("status") not in ("NO_TASK", "UNKNOWN_TASK"):
                self.get_logger().warning(
                    f"safety {etat} : tache {resultat.get('task_id')} -> {resultat.get('status')}")
            self.publish_state()

    def etat(self) -> dict:
        etat = dict(self.director.state())
        etat["safety"] = self.safety
        return etat

    def publish_state(self):
        # republié à chaque période, jamais seulement sur changement : un abonné tardif doit
        # voir l'état sans attendre un événement (un changement peut ne jamais venir).
        self.pub_state.publish(String(data=json.dumps(self.etat(), ensure_ascii=False)))


def main():
    rclpy.init()
    node = DirectorNode()
    node.get_logger().info("directeur pret")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
