"""Chaîne du bras en domaine 99 : exécutif -> MoveIt factice -> contrôleur réel -> pilote.

Trois pièces seulement sont simulées, et le minimum :

  - `FauxMoveGroup` sert `/move_action` : il lit la contrainte d'articulation, la
    transmet au contrôleur réel (comme le ferait `moveit_simple_controller_manager`)
    et rend le code MoveIt de succès. Il enregistre la demande reçue pour qu'on
    vérifie que l'exécutif ne transmet que des poses validées ;
  - `ArmTrajectoryServer` est le **vrai** nœud : il échantillonne la trajectoire et
    publie `/servo_ctrl` ;
  - `FauxPilote` joue `driver_node` : il recopie `/servo_ctrl` dans
    `/arm/servo_angles` à 10 Hz.

Rien ne bouge, aucun servo n'est branché, et le domaine 28 n'est jamais touché.

Vérifié ici : la pose validée arrive à MoveIt sous forme de contraintes, `arm_rest`
aboutit sur la chaîne réelle, une pose inconnue est refusée sans planification, un plan
refusé échoue sans toucher la pince, un retour servo muet fait échouer le skill en
cours, et un bras hors enveloppe bloque un skill de base.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

if os.environ.get("ROS_DOMAIN_ID") != "99":
    pytest.skip("test d'intégration : domaine 99 requis", allow_module_level=True)

RACINE = Path(__file__).resolve().parents[2]
for paquet in ("clawbot_executive", "clawbot_arm_controller", "clawbot_common"):
    sys.path.insert(0, str(RACINE / paquet))

import rclpy  # noqa: E402
from builtin_interfaces.msg import Duration  # noqa: E402
from control_msgs.action import FollowJointTrajectory  # noqa: E402
from moveit_msgs.action import MoveGroup  # noqa: E402
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse  # noqa: E402
from rclpy.callback_groups import ReentrantCallbackGroup  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy  # noqa: E402
from std_msgs.msg import Int32MultiArray, String  # noqa: E402
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint  # noqa: E402

from clawbot_arm_controller.arm_trajectory_server import ArmTrajectoryServer  # noqa: E402
from clawbot_interfaces.action import ExecuteSkill  # noqa: E402

from clawbot_executive.serveur import ServeurSkills  # noqa: E402

REGISTRE = RACINE / "clawbot_executive" / "config" / "skills.yaml"
POSES = RACINE / "config" / "arm_poses.yaml"
PRECONDITIONS = RACINE / "config" / "preconditions.yaml"
REPOS_DEG = [90, 180, 0, 0, 90, 149]
REPOS_RAD = [0.0, 1.570796, -1.570796, -1.570796, 0.0]

pytestmark = pytest.mark.integration


class FauxPilote(Node):
    """Recopie /servo_ctrl dans /arm/servo_angles, comme le pilote réel (10 Hz)."""

    def __init__(self):
        super().__init__("faux_pilote_bras")
        self.angles = list(REPOS_DEG)
        self.muet = False
        self.consignes = []
        self.create_subscription(Int32MultiArray, "/servo_ctrl", self._sur_consigne, 50)
        self._pub = self.create_publisher(Int32MultiArray, "/arm/servo_angles", 10)
        self.create_timer(0.1, self._publier)

    def _sur_consigne(self, message):
        if len(message.data) >= 2:
            self.consignes.append(list(message.data))
            numero, angle = int(message.data[0]), int(message.data[1])
            if 1 <= numero <= 6:
                self.angles[numero - 1] = angle

    def _publier(self):
        message = Int32MultiArray()
        message.data = [-1] * 6 if self.muet else list(self.angles)
        self._pub.publish(message)


class FauxMoveGroup(Node):
    """Sert /move_action ; transmet la contrainte au contrôleur réel."""

    def __init__(self):
        super().__init__("faux_move_group")
        self.demandes = []          # (group_name, {joint: (position, tolerance)})
        self.refuser = False
        self.client = ActionClient(self, FollowJointTrajectory,
                                   "/arm_controller/follow_joint_trajectory")
        self._serveur = ActionServer(
            self, MoveGroup, "/move_action", execute_callback=self._executer,
            goal_callback=lambda _g: GoalResponse.ACCEPT,
            cancel_callback=lambda _g: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

    def _executer(self, handle):
        requete = handle.request.request
        contraintes = {
            c.joint_name: (c.position, c.tolerance_above)
            for c in requete.goal_constraints[0].joint_constraints
        } if requete.goal_constraints else {}
        self.demandes.append((requete.group_name, contraintes))

        resultat = MoveGroup.Result()
        if self.refuser:
            resultat.error_code.val = -1                     # PLANNING_FAILED
            handle.abort()
            return resultat
        if not self.client.wait_for_server(timeout_sec=2.0):
            resultat.error_code.val = -4                     # CONTROL_FAILED
            handle.abort()
            return resultat

        trajectoire = JointTrajectory()
        trajectoire.joint_names = list(contraintes)
        point = JointTrajectoryPoint()
        point.positions = [contraintes[joint][0] for joint in trajectoire.joint_names]
        point.time_from_start = Duration(sec=1, nanosec=0)
        trajectoire.points = [point]
        objectif = FollowJointTrajectory.Goal()
        objectif.trajectory = trajectoire

        envoi = self.client.send_goal_async(objectif)
        handle_controleur = self._attendre(envoi, 3.0)
        ok = False
        if handle_controleur is not None and handle_controleur.accepted:
            resultat_controleur = handle_controleur.get_result_async()
            ok = self._attendre(resultat_controleur, 15.0) is not None

        resultat.error_code.val = 1 if ok else -4
        if ok:
            handle.succeed()
        else:
            handle.abort()
        return resultat

    @staticmethod
    def _attendre(future, timeout_s):
        fin = time.monotonic() + timeout_s
        while not future.done() and time.monotonic() < fin:
            time.sleep(0.02)
        return future.result() if future.done() else None


class Banc:
    def __init__(self):
        if not rclpy.ok():
            rclpy.init()
        self.executeur = MultiThreadedExecutor(num_threads=8)
        self.pilote = FauxPilote()
        self.controleur = ArmTrajectoryServer()
        self.move_group = FauxMoveGroup()
        self.serveur = ServeurSkills(registre=REGISTRE, preconditions=PRECONDITIONS,
                                     poses=POSES, nom="skill_server_p13")
        for noeud in (self.pilote, self.controleur, self.move_group, self.serveur):
            self.executeur.add_node(noeud)
        self._fil = threading.Thread(target=self.executeur.spin, daemon=True)
        self._fil.start()

        self.espion = Node("espion_p13")
        self.cmd_skill = []
        self.espion.create_subscription(
            __import__("geometry_msgs.msg", fromlist=["Twist"]).Twist,
            "/cmd_vel/skill", lambda m: self.cmd_skill.append((m.linear.x, m.linear.y,
                                                               m.angular.z)), 20)
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._pub_capa = self.espion.create_publisher(
            String, "/clawbot/capabilities/state", qos)
        self.executeur.add_node(self.espion)
        self.client = ActionClient(self.espion, ExecuteSkill, "/clawbot/execute_skill")

    def capacites(self, arm=True, base=True, lidar=True):
        actives = [nom for nom, actif in (("arm", arm), ("base", base), ("lidar", lidar)) if actif]
        message = String()
        message.data = json.dumps({"capabilities": [
            {"name": nom, "state": "ACTIVE", "units": [], "requires": [],
             "conflicts": [], "stale_flows": []} for nom in actives]})
        self._pub_capa.publish(message)

    def attendre_serveur(self):
        assert self.client.wait_for_server(timeout_sec=20.0), "serveur de skills injoignable"
        fin = time.monotonic() + 2.0
        while time.monotonic() < fin:
            self.capacites()
            time.sleep(0.05)

    def jouer(self, skill, params=None, timeout_s=30.0):
        from clawbot_interfaces.action import ExecuteSkill as Action

        objectif = Action.Goal()
        objectif.skill = skill
        objectif.params_json = json.dumps(params or {})
        objectif.timeout_s = timeout_s
        envoi = self.client.send_goal_async(objectif)
        fin = time.monotonic() + 10.0
        while not envoi.done() and time.monotonic() < fin:
            time.sleep(0.02)
        handle = envoi.result()
        assert handle.accepted, f"{skill} refusé"
        resultat = handle.get_result_async()
        fin = time.monotonic() + timeout_s + 10.0
        while not resultat.done() and time.monotonic() < fin:
            self.capacites()
            time.sleep(0.02)
        assert resultat.done(), f"{skill} sans résultat"
        return resultat.result().result

    def fermer(self):
        self.executeur.shutdown(timeout_sec=3.0)
        for noeud in (self.serveur, self.move_group, self.controleur, self.pilote, self.espion):
            noeud.destroy_node()


@pytest.fixture(scope="module")
def banc():
    banc = Banc()
    banc.attendre_serveur()
    yield banc
    banc.fermer()


# ── exécution réelle de bout en bout ─────────────────────────────────────────

@pytest.mark.req("REQ-ARM-002")
def test_joint_states_du_bras_a_au_moins_8_hz(banc):
    sonde = Node("sonde_arm_joint_states")

    from sensor_msgs.msg import JointState

    temps = []
    sonde.create_subscription(JointState, "/arm/joint_states",
                              lambda m: temps.append(time.monotonic()), 50)
    banc.executeur.add_node(sonde)
    time.sleep(3.0)
    banc.executeur.remove_node(sonde)
    sonde.destroy_node()

    assert len(temps) >= 24, f"{len(temps)} messages en 3 s (< 8 Hz)"
    if len(temps) > 1:
        cadence = (len(temps) - 1) / (temps[-1] - temps[0])
        assert cadence >= 8.0, cadence


@pytest.mark.req("REQ-ARM-003")
def test_arm_rest_confie_la_pose_validee_a_moveit_et_aboutit(banc):
    banc.pilote.angles = [90, 120, 0, 0, 90, 180]
    demandes = len(banc.move_group.demandes)
    resultat = banc.jouer("arm_rest")

    assert resultat.outcome == 0, resultat.message
    assert len(banc.move_group.demandes) == demandes + 1, "MoveIt n'a pas été appelé"
    groupe, contraintes = banc.move_group.demandes[-1]
    assert groupe == "arm"
    assert list(contraintes) == ["arm_joint1", "arm_joint2", "arm_joint3",
                                 "arm_joint4", "arm_joint5"]
    assert [contraintes[joint][0] for joint in contraintes] == pytest.approx(REPOS_RAD, abs=2e-3)
    # La tolérance transmise est celle de la pose validée (5 °), pas un chiffre inventé.
    assert all(abs(tolerance - 0.0872665) < 1e-5 for _, tolerance in contraintes.values())

    assert banc.pilote.angles == REPOS_DEG
    servo = {numero: angle for numero, angle in banc.pilote.consignes}
    assert servo.get(2) == 180 and servo.get(3) == 0


@pytest.mark.req("REQ-ARM-003")
def test_arm_named_pose_inconnue_refusee_sans_planification(banc):
    avant_poses = len(banc.move_group.demandes)
    avant_servos = len(banc.pilote.consignes)
    resultat = banc.jouer("arm_named_pose", {"pose": "inconnue"})

    assert resultat.outcome == 3, resultat.message          # REJECTED
    assert resultat.error_code == "INVALID_PARAMS"
    time.sleep(0.2)
    assert len(banc.move_group.demandes) == avant_poses, "une planification est partie"
    assert len(banc.pilote.consignes) == avant_servos, "une trajectoire est partie"


@pytest.mark.req("REQ-ARM-006")
def test_plan_refuse_echoue_sans_toucher_la_pince(banc):
    banc.move_group.refuser = True
    avant_servos = len(banc.pilote.consignes)
    try:
        resultat = banc.jouer("arm_rest")
    finally:
        banc.move_group.refuser = False

    assert resultat.outcome == 1, resultat.message
    assert resultat.error_code == "PLANNING_FAILED"
    assert len(banc.pilote.consignes) == avant_servos, "la pince a bougé après un plan refusé"


@pytest.mark.req("REQ-ARM-005")
def test_servo_muet_fait_echouer_le_skill_de_bras(banc):
    banc.pilote.muet = True
    try:
        time.sleep(0.8)                    # le pilote publie -1 depuis plus de 0,5 s
        debut = time.monotonic()
        resultat = banc.jouer("arm_named_pose", {"pose": "repos"}, timeout_s=10.0)
        ecoule = time.monotonic() - debut
    finally:
        banc.pilote.muet = False

    assert resultat.outcome == 1, resultat.message
    assert resultat.error_code == "SERVO_NO_FEEDBACK"
    assert ecoule < 2.0, f"échec trop tardif : {ecoule:.2f} s"


@pytest.mark.req("REQ-ARM-004")
def test_bras_hors_enveloppe_bloque_move_relative(banc):
    banc.pilote.angles = [90, 120, 0, 0, 90, 180]         # servo 2 hors bande
    avant = len(banc.cmd_skill)
    try:
        time.sleep(0.8)
        resultat = banc.jouer("move_relative", {"dx_m": 0.05}, timeout_s=5.0)
    finally:
        banc.pilote.angles = list(REPOS_DEG)

    assert resultat.outcome == 1, resultat.message
    assert resultat.error_code == "ARM_NOT_AT_REST"
    # Le serveur publie une consigne nulle en fin de goal (filet d'arrêt) : ce n'est pas
    # un déplacement. Ce qui est interdit ici, c'est une consigne non nulle.
    assert all(consigne == (0.0, 0.0, 0.0) for consigne in banc.cmd_skill[avant:]), \
        "une consigne de déplacement est partie"
