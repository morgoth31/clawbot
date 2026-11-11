"""Traduction d'une étape déclarée en goal d'action réel.

Le directeur ne fabrique aucun geste : il envoie un goal au serveur d'action du skill, attend le
résultat, et avance sur ce résultat. Cette table est la seule surface où un nom de skill devient
un goal ; S2 ne fournit qu'un nom et des arguments bornés, jamais un topic ni un goal brut.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
from nav2_msgs.action import NavigateToPose
from trajectory_msgs.msg import JointTrajectoryPoint

from . import waypoints as catalogue_waypoints

MAX_TIMEOUT_S = 120.0
TIMEOUT_PAR_DEFAUT_S = 30.0

BRAS = {
    "action": "/arm_controller/follow_joint_trajectory",
    "joints": ["arm_joint1", "arm_joint2", "arm_joint3", "arm_joint4", "arm_joint5"],
    "bornes_rad": (-1.5708, 3.14159),
}
PINCE = {
    "action": "/grip_controller/follow_joint_trajectory",
    "joints": ["grip_joint"],
    "bornes_rad": (-1.54, 0.0),
}
# Une navigation dure plus longtemps qu'un geste de bras : la pièce fait 4 m de long et la base
# avance à 0,10 m/s au mieux, soit ~40 s de trajet plus les reculs de dégagement de Nav2.
NAVIGATION = {
    "action": "/navigate_to_pose",
    "timeout_s": 90.0,
}
# Clés qu'un appelant ne doit jamais pouvoir glisser dans args : elles décriraient une pose, et
# une pose libre venue de S2 est exactement ce que le contrat interdit.
CLES_POSE_INTERDITES = ("x", "y", "z", "yaw", "theta", "pose", "position", "coordonnees")



class SkillInconnu(ValueError):
    """Nom de skill absent de la table : refusé avant tout envoi."""


class SkillInvalide(ValueError):
    """Arguments hors bornes ou mal formés : refusé avant tout envoi."""


class SkillIndisponible(RuntimeError):
    """Skill déclaré mais dont l'implémentation n'existe pas encore dans cette version."""


@dataclass(frozen=True)
class Plan:
    """Ce qu'il faut envoyer : action, type, goal construit, délai d'attente."""

    action: str
    type_action: type
    goal: object
    timeout_s: float


def _duree(args: dict) -> float:
    valeur = args.get("duration_s", 2.0)
    try:
        duree = float(valeur)
    except (TypeError, ValueError) as exc:
        raise SkillInvalide(f"duration_s doit etre un nombre : {valeur!r}") from exc
    if not 0.5 <= duree <= 10.0:
        raise SkillInvalide(f"duration_s hors bornes [0.5, 10] : {duree}")
    return duree


def _delai(args: dict) -> float:
    valeur = args.get("timeout_s", TIMEOUT_PAR_DEFAUT_S)
    try:
        delai = float(valeur)
    except (TypeError, ValueError) as exc:
        raise SkillInvalide(f"timeout_s doit etre un nombre : {valeur!r}") from exc
    if not 0.1 <= delai <= MAX_TIMEOUT_S:
        raise SkillInvalide(f"timeout_s hors bornes [0.1, {MAX_TIMEOUT_S:g}] : {delai}")
    return delai


def _goal_trajectoire(spec: dict, positions: list, duree: float):
    bas, haut = spec["bornes_rad"]
    if not isinstance(positions, list) or len(positions) != len(spec["joints"]):
        raise SkillInvalide(f"positions doit contenir {len(spec['joints'])} valeurs")
    for valeur in positions:
        if not isinstance(valeur, (int, float)) or not bas <= float(valeur) <= haut:
            raise SkillInvalide(f"position hors bornes [{bas}, {haut}] rad : {valeur!r}")

    point = JointTrajectoryPoint()
    point.positions = [float(v) for v in positions]
    point.time_from_start = Duration(sec=int(duree), nanosec=int(round((duree % 1) * 1e9)))

    goal = FollowJointTrajectory.Goal()
    goal.trajectory.joint_names = list(spec["joints"])
    goal.trajectory.points = [point]
    return goal


def _plan_bras(args: dict) -> Plan:
    return Plan(BRAS["action"], FollowJointTrajectory,
                _goal_trajectoire(BRAS, args.get("positions"), _duree(args)), _delai(args))


def _plan_pince(args: dict) -> Plan:
    position = args.get("position")
    return Plan(PINCE["action"], FollowJointTrajectory,
                _goal_trajectoire(PINCE, [position], _duree(args)), _delai(args))


def _delai_navigation(args: dict) -> float:
    valeur = args.get("timeout_s", NAVIGATION["timeout_s"])
    try:
        delai = float(valeur)
    except (TypeError, ValueError) as exc:
        raise SkillInvalide(f"timeout_s doit etre un nombre : {valeur!r}") from exc
    if not 1.0 <= delai <= MAX_TIMEOUT_S:
        raise SkillInvalide(f"timeout_s de navigation hors bornes [1, {MAX_TIMEOUT_S:g}] : {delai}")
    return delai


def _plan_navigation(args: dict, catalogue=None) -> Plan:
    """Adaptateur `navigate_to` -> goal `NavigateToPose` de Nav2.

    L'entrée n'est qu'un nom : `destination` doit figurer dans l'énumération fermée du catalogue.
    Tout ce qui ressemble à une pose est refusé ici, avant qu'un goal existe — c'est le seul point
    où une coordonnée pourrait entrer dans le système, il ferme la porte.
    """
    presentes = [cle for cle in CLES_POSE_INTERDITES if cle in args]
    if presentes:
        raise SkillInvalide(
            f"coordonnees libres refusees ({', '.join(presentes)}) : la destination est un "
            "waypoint du catalogue, jamais une pose")
    destination = args.get("destination")
    if destination is None:
        raise SkillInvalide(
            "destination attendue : nom de waypoint du catalogue "
            f"({catalogue_waypoints.chemin_par_defaut()})")

    catalogue = catalogue if catalogue is not None else catalogue_waypoints.charger()
    try:
        waypoint = catalogue.resoudre(destination)
    except ValueError as exc:            # WaypointInconnu et WaypointInvalide
        raise SkillInvalide(str(exc)) from exc

    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = catalogue.frame
    # horodatage nul : Nav2 résout la pose par rapport à la TF la plus récente, ce qui évite de
    # dépendre de l'horloge de ce processus pour une cible statique.
    goal.pose.pose.position.x = waypoint.x
    goal.pose.pose.position.y = waypoint.y
    goal.pose.pose.position.z = 0.0
    goal.pose.pose.orientation.z = math.sin(waypoint.yaw / 2.0)
    goal.pose.pose.orientation.w = math.cos(waypoint.yaw / 2.0)
    return Plan(NAVIGATION["action"], NavigateToPose, goal, _delai_navigation(args))



def _indisponible(message: str):
    def _refus(_args: dict) -> Plan:
        raise SkillIndisponible(message)
    return _refus


REGISTRE = {
    "arm_move": _plan_bras,
    "grip_set": _plan_pince,
    "navigate_to": _plan_navigation,
    "follow_human": _indisponible("asservissement visuel absent (lot 6)"),
    "grasp_object": _indisponible("perception et saisie absentes (lot 6)"),
    "search_object": _indisponible("balayage et detection absents (lot 6)"),
    "express_state": _indisponible("LED et buzzer non cables (lot 7)"),
    "look_at_board": _indisponible("hors perimetre de cette version (echecs)"),
    "set_watch_mode": _indisponible("sentinel absent (lot 4)"),
}


def construire_plan(etape: dict, catalogue=None) -> Plan:
    """Plan d'exécution d'une étape ; lève avant tout effet si l'étape est refusable.

    `catalogue` n'existe que pour les tests : en service, les waypoints sont lus depuis
    `config/waypoints.yaml`, jamais fournis par un appelant.
    """
    if not isinstance(etape, dict):
        raise SkillInvalide("etape doit etre un objet")
    skill = etape.get("skill")
    fabrique = REGISTRE.get(skill)
    if fabrique is None:
        raise SkillInconnu(f"skill inconnu : {skill!r}")
    args = etape.get("args") or {}
    if not isinstance(args, dict):
        raise SkillInvalide(f"{skill} : args doit etre un objet")
    if fabrique is _plan_navigation:
        return fabrique(args, catalogue)
    return fabrique(args)
