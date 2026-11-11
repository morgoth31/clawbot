"""Faux contrôleur de bras pour les tests, en domaine 99.

Trois modes : `succes` (goal accepté et réussi), `echec` (abort immédiat), `silencieux` (goal
accepté qui ne rend jamais la main, pour éprouver délai et annulation). Le groupe réentrant est
obligatoire : sans lui, une requête d'annulation ne peut pas être traitée pendant que le
callback d'exécution tourne, et le test conclurait à tort que l'annulation ne marche pas.
"""

from __future__ import annotations

import threading
import time

from rclpy.action import ActionServer
from rclpy.action.server import CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from control_msgs.action import FollowJointTrajectory

ACTION_BRAS = '/arm_controller/follow_joint_trajectory'


class FauxBras:
    def __init__(self, mode: str = 'succes'):
        self.node = Node('faux_bras')
        self.mode = mode
        self.recus = 0
        self.annules = 0
        self.goals = []
        self._serveur = ActionServer(
            self.node, FollowJointTrajectory, ACTION_BRAS, self._executer,
            callback_group=ReentrantCallbackGroup(),
            # rclpy refuse les annulations par défaut : sans ce callback, le goal reste
            # actif et tout test d'annulation conclut à tort que le directeur n'annule pas
            cancel_callback=lambda _objectif: CancelResponse.ACCEPT)
        self._executeur = MultiThreadedExecutor(num_threads=3)
        self._executeur.add_node(self.node)
        threading.Thread(target=self._executeur.spin, daemon=True).start()
        time.sleep(0.5)   # découverte DDS avant que le directeur n'envoie un goal

    def _executer(self, objectif):
        self.recus += 1
        self.goals.append(objectif.request)
        if self.mode == 'echec':
            objectif.abort()
            return FollowJointTrajectory.Result()
        if self.mode == 'silencieux':
            fin = time.monotonic() + 30.0
            while time.monotonic() < fin:
                if objectif.is_cancel_requested:
                    self.annules += 1
                    objectif.canceled()
                    return FollowJointTrajectory.Result()
                time.sleep(0.01)
            objectif.abort()
            return FollowJointTrajectory.Result()
        objectif.succeed()
        return FollowJointTrajectory.Result()

    def fermer(self):
        # arrêter le spin AVANT de détruire les entités : détruire un serveur pendant que
        # l'executor tourne fait tomber le processus (abort rclcpp, pas une exception)
        self._executeur.shutdown()
        self._serveur.destroy()
        self.node.destroy_node()
