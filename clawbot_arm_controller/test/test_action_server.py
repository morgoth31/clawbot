"""Test de contrat du serveur d'action, sans materiel.

Le noeud est lance dans le processus de test sur un domaine DDS isole : /servo_ctrl n'a
alors aucun abonne (le pilote du bras tourne sur le domaine 28), donc rien ne bouge.
Ce que ce test prouve : l'action accepte une trajectoire, l'echantillonne et publie une
consigne par servo, dans l'ordre et jusqu'au point final. Il ne prouve pas que le bras
atteint la position.
"""

import math
import os
import time

import pytest

os.environ.setdefault('ROS_DOMAIN_ID', '99')

rclpy = pytest.importorskip('rclpy')
from rclpy.action import ActionClient  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from builtin_interfaces.msg import Duration  # noqa: E402
from control_msgs.action import FollowJointTrajectory  # noqa: E402
from sensor_msgs.msg import JointState  # noqa: E402
from std_msgs.msg import Int32MultiArray  # noqa: E402
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint  # noqa: E402

from clawbot_arm_controller.arm_trajectory_server import (  # noqa: E402
    ArmTrajectoryServer,
    SUCCESSFUL,
)


def _point(positions, seconds):
    point = JointTrajectoryPoint()
    point.positions = [float(q) for q in positions]
    point.time_from_start = Duration(
        sec=int(seconds), nanosec=int(round((seconds - int(seconds)) * 1e9)))
    return point


@pytest.fixture()
def stack():
    if not rclpy.ok():        # contexte partagé par la session de test
        rclpy.init()
    node = ArmTrajectoryServer()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    probe = Node('probe')
    servos = []
    states = []
    probe.create_subscription(Int32MultiArray, '/servo_ctrl',
                              lambda m: servos.append(list(m.data)), 50)
    probe.create_subscription(JointState, '/arm/joint_states',
                              lambda m: states.append(dict(zip(m.name, m.position))), 50)
    executor.add_node(probe)

    import threading
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    time.sleep(1.0)
    try:
        yield node, probe, servos, states
    finally:
        executor.shutdown()
        node.destroy_node()
        probe.destroy_node()
        # contexte partagé : ne pas l'éteindre entre deux fichiers


def _send(probe, action_name, joint_names, points, timeout_s=15.0):
    client = ActionClient(probe, FollowJointTrajectory, action_name)
    assert client.wait_for_server(timeout_sec=timeout_s), 'serveur d action absent'
    goal = FollowJointTrajectory.Goal()
    goal.trajectory = JointTrajectory()
    goal.trajectory.joint_names = joint_names
    goal.trajectory.points = points
    future = client.send_goal_async(goal)
    deadline = time.time() + timeout_s
    while not future.done() and time.time() < deadline:
        time.sleep(0.02)
    handle = future.result()
    return client, handle


def test_trajectoire_du_bras_aboutit_et_emet_les_consignes(stack):
    node, probe, servos, states = stack
    _, handle = _send(
        probe, '/arm_controller/follow_joint_trajectory',
        ['arm_joint1', 'arm_joint2', 'arm_joint3', 'arm_joint4', 'arm_joint5'],
        [_point([0.0] * 5, 0.0), _point([0.5, -0.5, 0.5, -0.5, 0.5], 0.6)])

    assert handle.accepted, 'objectif refuse'
    result = handle.get_result_async()
    deadline = time.time() + 20.0
    while not result.done() and time.time() < deadline:
        time.sleep(0.02)
    assert result.done(), 'aucun resultat'
    assert result.result().result.error_code == SUCCESSFUL

    ids = {data[0] for data in servos}
    assert ids == {1, 2, 3, 4, 5}, f'servos commandes: {sorted(ids)}'
    for data in servos:
        assert 0 <= data[1] <= 270

    final = {data[0]: data[1] for data in servos}
    assert final[1] == 119, final  # 90 + 28,648°
    assert final[2] == 61, final   # 90 - 28,648°
    # `/arm/joint_states` est publié à 20 Hz par un minuteur, indépendamment de la fin de
    # la trajectoire : le dernier message reçu au moment du résultat peut précéder le
    # point final (course observée dans la suite complète, 0,417 rad au lieu de 0,5).
    # On attend le message qui porte la position finale, avec échéance — l'assertion reste
    # la même.
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if states and states[-1].get('arm_joint1') == pytest.approx(0.5, abs=1e-3):
            break
        time.sleep(0.02)
    assert states and set(states[-1]) == {
        'arm_joint1', 'arm_joint2', 'arm_joint3', 'arm_joint4', 'arm_joint5',
        'grip_joint'}
    assert states[-1]['arm_joint1'] == pytest.approx(0.5, abs=1e-3)


def test_objectif_avec_mauvaises_articulations_refuse(stack):
    node, probe, servos, states = stack
    client, handle = _send(
        probe, '/arm_controller/follow_joint_trajectory',
        ['joint1', 'joint2', 'joint3', 'joint4', 'joint5'],
        [_point([0.0] * 5, 0.1)])
    assert not handle.accepted


def test_pince_aboutit_et_ferme(stack):
    node, probe, servos, states = stack
    _, handle = _send(
        probe, '/grip_controller/follow_joint_trajectory', ['grip_joint'],
        [_point([-1.0], 0.0), _point([0.0], 0.3)])
    assert handle.accepted
    result = handle.get_result_async()
    deadline = time.time() + 15.0
    while not result.done() and time.time() < deadline:
        time.sleep(0.02)
    assert result.result().result.error_code == SUCCESSFUL
    grip = [data[1] for data in servos if data[0] == 6]
    assert grip, 'aucune consigne sur le servo 6'
    assert grip[-1] == 180


def test_annulation_arrete_la_publication(stack):
    node, probe, servos, states = stack
    client, handle = _send(
        probe, '/arm_controller/follow_joint_trajectory',
        ['arm_joint1', 'arm_joint2', 'arm_joint3', 'arm_joint4', 'arm_joint5'],
        [_point([0.0] * 5, 0.0), _point([0.9] * 5, 3.0)])
    assert handle.accepted
    time.sleep(0.6)
    handle.cancel_goal_async()
    result = handle.get_result_async()
    deadline = time.time() + 10.0
    while not result.done() and time.time() < deadline:
        time.sleep(0.02)
    assert result.result().status == 5  # STATUS_CANCELED
    count_at_cancel = len(servos)
    time.sleep(0.6)
    assert len(servos) == count_at_cancel, 'des consignes sont parties apres annulation'
