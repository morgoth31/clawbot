"""Envoi des trajectoires du bras : action FollowJointTrajectory (P13).

Un seul chemin d'exécution : l'action du contrôleur de trajectoire
(`clawbot_arm_controller`). Les poses nommées sont des configurations articulaires
fixes, il n'y a rien à planifier ; passer par MoveIt ajouterait une planification et
un état courant dont le bras n'a pas besoin.

La surveillance du retour servo s'exécute pendant la trajectoire : dès qu'un servo ne
répond plus depuis plus de 0,5 s, le goal est annulé et le skill échoue
`SERVO_NO_FEEDBACK` (REQ-ARM-005). Un servo muet ne doit pas se terminer en
`SUCCEEDED` sur une consigne supposée appliquée.
"""

from __future__ import annotations

import time

from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionClient
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from .bras import Issue

# groupe -> (nom d'action, articulations attendues par le serveur)
GROUPES = {
    "arm": ("/arm_controller/follow_joint_trajectory",
            ["arm_joint1", "arm_joint2", "arm_joint3", "arm_joint4", "arm_joint5"]),
    "grip": ("/grip_controller/follow_joint_trajectory", ["grip_joint"]),
}

ATTENTE_SERVEUR_S = 3.0
PERIODE_SURVEILLANCE_S = 0.05
MARGE_ECHEC_S = 5.0


class ExecuteurActions:
    """Client d'action du bras et de la pince, avec surveillance du retour servo."""

    def __init__(self, node, etats=None):
        self.node = node
        self.etats = etats
        self.clients = {
            groupe: ActionClient(node, FollowJointTrajectory, action)
            for groupe, (action, _joints) in GROUPES.items()
        }
        self._annulations: list = []

    def prets(self) -> bool:
        return all(client.server_is_ready() for client in self.clients.values())

    def executer(self, groupe, positions, duree_s, timeout_s, surveillance=None) -> Issue:
        if groupe not in GROUPES:
            return Issue(False, "INVALID_PARAMS", f"groupe inconnu : {groupe!r}")
        action, joints = GROUPES[groupe]
        if len(positions) != len(joints):
            return Issue(False, "INVALID_PARAMS",
                         f"{groupe} : {len(positions)} positions pour {len(joints)} articulations")
        client = self.clients[groupe]
        if not client.wait_for_server(timeout_sec=ATTENTE_SERVEUR_S):
            return Issue(False, "CAPABILITY_INACTIVE", f"serveur d'action {action} injoignable")

        trajectoire = JointTrajectory()
        trajectoire.joint_names = list(joints)
        point = JointTrajectoryPoint()
        point.positions = [float(q) for q in positions]
        secondes = max(0.0, float(duree_s))
        point.time_from_start = Duration(
            sec=int(secondes), nanosec=int(round((secondes - int(secondes)) * 1e9)))
        trajectoire.points = [point]

        objectif = FollowJointTrajectory.Goal()
        objectif.trajectory = trajectoire

        envoi = client.send_goal_async(objectif)
        handle = self._attendre(envoi, min(ATTENTE_SERVEUR_S, max(1.0, timeout_s)))
        if handle is None:
            return Issue(False, "TIMEOUT", f"{action} : envoi du goal sans réponse")
        if not handle.accepted:
            return Issue(False, "ARM_GOAL_REFUSED", f"{action} a refusé le goal")

        resultat = handle.get_result_async()
        debut = time.monotonic()
        while not resultat.done():
            if time.monotonic() - debut > timeout_s + MARGE_ECHEC_S:
                self._annuler(handle)
                self._attendre(resultat, 2.0)     # laisse le goal se poser avant de rendre
                return Issue(False, "TIMEOUT", f"{action} : trajectoire non terminée")
            if surveillance is not None:
                code = surveillance()
                if code:
                    self._annuler(handle)
                    return Issue(False, code, "retour servo invalide : trajectoire annulée")
            time.sleep(PERIODE_SURVEILLANCE_S)

        issue = resultat.result()
        resultat_action = getattr(issue, "result", None)
        if resultat_action is not None and getattr(resultat_action, "error_code", 0) != 0:
            return Issue(False, "ARM_TRAJECTORY_FAILED",
                         f"{action} : {resultat_action.error_string or 'échec'}")
        if getattr(issue, "status", None) not in (4, None):     # 4 = STATUS_SUCCEEDED
            return Issue(False, "ARM_TRAJECTORY_FAILED", f"{action} : goal non abouti")
        return Issue(True)

    @staticmethod
    def _attendre(future, timeout_s: float):
        fin = time.monotonic() + timeout_s
        while not future.done() and time.monotonic() < fin:
            time.sleep(0.02)
        if not future.done():
            return None
        try:
            return future.result()
        except Exception:                                     # noqa: BLE001
            return None

    def _annuler(self, handle) -> None:
        """Annule le goal en gardant la référence du future.

        Sans référence, rclpy libère le future d'annulation et l'exception qu'il porte
        (« 'NoneType' object has no attribute 'trigger' ») est rapportée plus tard,
        hors contexte, comme exception jamais récupérée.
        """
        futur = handle.cancel_goal_async()
        self._annulations.append(futur)
        futur.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
