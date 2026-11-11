"""Faux serveur d'action `NavigateToPose` pour les tests, en domaine 99.

Il ne planifie pas : il accuse réception, puis réussit (ou échoue, ou se tait). Son intérêt est
de journaliser la pose exacte demandée, ce qui permet d'affirmer que le directeur envoie bien la
pose du catalogue et pas une coordonnée venue d'ailleurs.

Le groupe de callbacks réentrant et le `cancel_callback` explicite sont obligatoires : sans eux,
une demande d'annulation ne peut pas être traitée pendant l'exécution, et tout test d'annulation
conclurait à tort que le directeur n'annule pas.
"""

from __future__ import annotations

import threading
import time

from rclpy.action import ActionServer
from rclpy.action.server import CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from nav2_msgs.action import NavigateToPose

ACTION_NAVIGATION = "/navigate_to_pose"


class FauxNavigateur:
    def __init__(self, mode: str = "succes"):
        self.node = Node("faux_navigateur")
        self.mode = mode
        self.recus = 0
        self.annules = 0
        self.goals = []
        self._serveur = ActionServer(
            self.node, NavigateToPose, ACTION_NAVIGATION, self._executer,
            callback_group=ReentrantCallbackGroup(),
            cancel_callback=lambda _objectif: CancelResponse.ACCEPT)
        self._executeur = MultiThreadedExecutor(num_threads=3)
        self._executeur.add_node(self.node)
        threading.Thread(target=self._executeur.spin, daemon=True).start()
        time.sleep(0.5)   # découverte DDS avant que le directeur n'envoie un goal

    def _executer(self, objectif):
        self.recus += 1
        self.goals.append(objectif.request)
        if self.mode == "echec":
            objectif.abort()
            return NavigateToPose.Result()
        if self.mode == "silencieux":
            fin = time.monotonic() + 30.0
            while time.monotonic() < fin:
                if objectif.is_cancel_requested:
                    self.annules += 1
                    objectif.canceled()
                    return NavigateToPose.Result()
                time.sleep(0.01)
            objectif.abort()
            return NavigateToPose.Result()
        objectif.succeed()
        return NavigateToPose.Result()

    def fermer(self):
        # arrêter le spin AVANT de détruire les entités : détruire un serveur pendant que
        # l'executor tourne fait tomber le processus (abort rclcpp, pas une exception)
        self._executeur.shutdown()
        self._serveur.destroy()
        self.node.destroy_node()
