"""Verification du mode `passive_joints` : aucun ordre ne doit partir vers le servo.

Contexte reel : le servo 4 du bras renvoie un angle invalide (-5 deg) ; le commander
risquerait un saut. La trajectoire peut donc porter sa valeur sans qu'aucune consigne ne
parte sur /servo_ctrl, tout en la publiant dans /arm/joint_states.
"""

import os
import threading
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

JOINTS = ['arm_joint1', 'arm_joint2', 'arm_joint3', 'arm_joint4', 'arm_joint5']


def _point(positions, seconds):
    point = JointTrajectoryPoint()
    point.positions = [float(q) for q in positions]
    point.time_from_start = Duration(
        sec=int(seconds), nanosec=int(round((seconds - int(seconds)) * 1e9)))
    return point


def test_le_servo_passif_ne_recoit_aucune_consigne():
    rclpy.init(args=['--ros-args', '-p', 'passive_joints:=["arm_joint4"]'])
    node = ArmTrajectoryServer()
    assert node._passive == {'arm_joint4'}, 'parametre passive_joints non applique'

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    probe = Node('probe_passive')
    servos = []
    states = []
    probe.create_subscription(Int32MultiArray, '/servo_ctrl',
                              lambda m: servos.append(list(m.data)), 50)
    probe.create_subscription(JointState, '/arm/joint_states',
                              lambda m: states.append(dict(zip(m.name, m.position))), 50)
    executor.add_node(probe)
    threading.Thread(target=executor.spin, daemon=True).start()
    time.sleep(1.0)

    try:
        client = ActionClient(probe, FollowJointTrajectory,
                              '/arm_controller/follow_joint_trajectory')
        assert client.wait_for_server(timeout_sec=10.0)
        goal = FollowJointTrajectory.Goal()
        goal.trajectory = JointTrajectory()
        goal.trajectory.joint_names = JOINTS
        goal.trajectory.points = [
            _point([0.0, 0.0, 0.0, 0.0, 0.0], 0.0),
            _point([0.0, 0.0, 0.0, 0.6, 0.0], 0.5),
        ]
        send = client.send_goal_async(goal)
        deadline = time.time() + 15.0
        while not send.done() and time.time() < deadline:
            time.sleep(0.02)
        handle = send.result()
        assert handle is not None and handle.accepted
        result = handle.get_result_async()
        deadline = time.time() + 15.0
        while not result.done() and time.time() < deadline:
            time.sleep(0.02)
        assert result.result().result.error_code == SUCCESSFUL
        time.sleep(0.4)  # laisser le minuteur /arm/joint_states publier la position finale

        assert not [data for data in servos if data[0] == 4], \
            f'le servo 4 a recu une consigne alors qu il est passif : {servos}'
        assert states, 'aucun /arm/joint_states publie'
        assert states[-1]['arm_joint4'] == pytest.approx(0.6, abs=1e-6), \
            'l articulation passive doit rester suivie dans /arm/joint_states'
    finally:
        executor.shutdown()
        node.destroy_node()
        probe.destroy_node()
        rclpy.shutdown()
