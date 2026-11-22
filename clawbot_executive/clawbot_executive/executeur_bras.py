"""Exécution des poses du bras par MoveIt 2 (P13, décision opérateur du 2026-11-22).

Une pose nommée est une configuration articulaire fixe : MoveIt la reçoit comme une
contrainte d'articulation (position ± tolérance validée), planifie avec le pipeline
`ompl` et exécute la trajectoire sur `arm_controller` — le serveur d'action que
`moveit_controllers.yaml` déclare, qui publie sur `/servo_ctrl`.

Pourquoi MoveIt et pas l'action du contrôleur directement : c'est lui qui porte les
poses (`group_state` du SRDF, générées depuis `config/arm_poses.yaml`), la vérification
de collision et les limites de vitesse du modèle. L'exécutif ne calcule aucun angle :
il transmet une pose validée.

Deux choses que MoveIt ne fait pas à notre place :

  - **la pince** : un seul axe, deux butées validées, aucune planification utile ;
    elle est commandée directement sur `grip_controller` ;
  - **la preuve du mouvement** : le contrôleur ne reçoit aucun retour de position, ses
    `/arm/joint_states` sont des consignes. La vérification finale se fait sur
    `/arm/servo_angles` (REQ-ARM-006), et la surveillance d'un servo muet pendant la
    trajectoire annule le goal (REQ-ARM-005).
"""

from __future__ import annotations

import time

from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import Constraints, JointConstraint
from rclpy.action import ActionClient
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from .bras import Issue

MOVE_ACTION = "/move_action"
GROUPE_BRAS = "arm"
ACTION_PINCE = "/grip_controller/follow_joint_trajectory"
JOINTS_PINCE = ["grip_joint"]

ATTENTE_SERVEUR_S = 3.0
PERIODE_SURVEILLANCE_S = 0.05
MARGE_ECHEC_S = 10.0
MAX_PLANIFICATION_S = 5.0

SUCCES_MOVEIT = 1
CONTROLE_ECHOUE = -4
DELAI_DEPASSE = -6


class ExecuteurMoveIt:
    """Planie et exécute une pose validée par MoveIt, et commande la pince."""

    def __init__(self, node, etats=None):
        self.node = node
        self.etats = etats
        self.client_move = ActionClient(node, MoveGroup, MOVE_ACTION)
        self.client_pince = ActionClient(node, FollowJointTrajectory, ACTION_PINCE)
        self._annulations: list = []

    def prets(self) -> bool:
        return self.client_move.server_is_ready() and self.client_pince.server_is_ready()

    # ── pose du bras, par MoveIt ─────────────────────────────────────────────
    @staticmethod
    def objectif_moveit(contraintes) -> MoveGroup.Goal:
        """Objectif MoveGroup pour une liste de (articulation, position, tolérance)."""
        objectif = MoveGroup.Goal()
        requete = objectif.request
        requete.group_name = GROUPE_BRAS
        requete.num_planning_attempts = 3
        requete.allowed_planning_time = MAX_PLANIFICATION_S
        requete.max_velocity_scaling_factor = 1.0
        requete.max_acceleration_scaling_factor = 1.0

        but = Constraints()
        for joint, position, tolerance in contraintes:
            contrainte = JointConstraint()
            contrainte.joint_name = joint
            contrainte.position = float(position)
            contrainte.tolerance_above = float(tolerance)
            contrainte.tolerance_below = float(tolerance)
            contrainte.weight = 1.0
            but.joint_constraints.append(contrainte)
        requete.goal_constraints = [but]

        objectif.planning_options.plan_only = False
        objectif.planning_options.replan = False
        return objectif

    def executer_pose(self, contraintes, timeout_s, surveillance=None) -> Issue:
        if not self.client_move.wait_for_server(timeout_sec=ATTENTE_SERVEUR_S):
            return Issue(False, "CAPABILITY_INACTIVE",
                         f"planificateur {MOVE_ACTION} injoignable (move_group arrêté ?)")

        envoi = self.client_move.send_goal_async(self.objectif_moveit(contraintes))
        handle = self._attendre(envoi, min(ATTENTE_SERVEUR_S, max(1.0, timeout_s)))
        if handle is None:
            return Issue(False, "TIMEOUT", f"{MOVE_ACTION} : envoi du goal sans réponse")
        if not handle.accepted:
            return Issue(False, "PLANNING_FAILED", "move_group a refusé le goal")

        resultat = handle.get_result_async()
        issue = self._suivre(resultat, handle, timeout_s + MAX_PLANIFICATION_S, surveillance)
        if issue is not None:
            return issue
        return self._lire_resultat_moveit(resultat.result())

    # ── pince, par le contrôleur ─────────────────────────────────────────────
    def executer_pince(self, position_rad, duree_s, timeout_s, surveillance=None) -> Issue:
        if not self.client_pince.wait_for_server(timeout_sec=ATTENTE_SERVEUR_S):
            return Issue(False, "CAPABILITY_INACTIVE",
                         f"serveur d'action {ACTION_PINCE} injoignable")

        trajectoire = JointTrajectory()
        trajectoire.joint_names = list(JOINTS_PINCE)
        point = JointTrajectoryPoint()
        point.positions = [float(position_rad)]
        secondes = max(0.0, float(duree_s))
        point.time_from_start = Duration(
            sec=int(secondes), nanosec=int(round((secondes - int(secondes)) * 1e9)))
        trajectoire.points = [point]
        objectif = FollowJointTrajectory.Goal()
        objectif.trajectory = trajectoire

        envoi = self.client_pince.send_goal_async(objectif)
        handle = self._attendre(envoi, min(ATTENTE_SERVEUR_S, max(1.0, timeout_s)))
        if handle is None:
            return Issue(False, "TIMEOUT", f"{ACTION_PINCE} : envoi du goal sans réponse")
        if not handle.accepted:
            return Issue(False, "INVALID_PARAMS", f"{ACTION_PINCE} a refusé le goal")

        resultat = handle.get_result_async()
        issue = self._suivre(resultat, handle, timeout_s + MARGE_ECHEC_S, surveillance)
        if issue is not None:
            return issue
        retour = resultat.result().result
        if getattr(retour, "error_code", 0) != 0:
            return Issue(False, "GOAL_UNREACHABLE",
                         f"{ACTION_PINCE} : {retour.error_string or 'échec'}")
        return Issue(True)

    # ── outillage ────────────────────────────────────────────────────────────
    def _suivre(self, resultat, handle, budget_s, surveillance):
        """Attend le résultat en surveillant le retour servo ; None si abouti."""
        debut = time.monotonic()
        while not resultat.done():
            if time.monotonic() - debut > budget_s:
                self._annuler(handle, resultat)
                return Issue(False, "TIMEOUT", "trajectoire non terminée dans le budget")
            if surveillance is not None:
                code = surveillance()
                if code:
                    self._annuler(handle, resultat)
                    return Issue(False, code, "retour servo invalide : trajectoire annulée")
            time.sleep(PERIODE_SURVEILLANCE_S)
        return None

    def _annuler(self, handle, resultat) -> None:
        """Annule le goal en gardant les futures : sinon rclpy les libère et rapporte
        leur exception plus tard, hors contexte (« cannot use Destroyable… »)."""
        futur = handle.cancel_goal_async()
        self._annulations.append(futur)
        futur.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
        self._attendre(resultat, 2.0)                 # laisse le goal se poser

    @staticmethod
    def _lire_resultat_moveit(issue) -> Issue:
        resultat = getattr(issue, "result", None)
        code = getattr(getattr(resultat, "error_code", None), "val", None)
        if code == SUCCES_MOVEIT:
            return Issue(True)
        if code == CONTROLE_ECHOUE:
            return Issue(False, "GOAL_UNREACHABLE",
                         f"le contrôleur n'a pas exécuté le plan (code MoveIt {code})")
        if code == DELAI_DEPASSE:
            return Issue(False, "TIMEOUT", f"planification hors délai (code MoveIt {code})")
        return Issue(False, "PLANNING_FAILED",
                     f"aucun plan exécutable (code MoveIt {code}) : "
                     "pose en collision, hors limites ou non atteignable")

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
