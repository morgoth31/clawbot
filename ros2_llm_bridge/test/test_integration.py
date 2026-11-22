import os
import sys
import unittest
import launch
import launch_ros
import launch_testing
import launch_testing.actions
import pytest
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

pytestmark = pytest.mark.xfail(strict=True, reason=(
    "exige la fixture launch_testing proc_output, indisponible quand l'autochargement"
    " des plugins ROS est coupé : à exécuter via launch_testing, pas ici (REQ-TEST-001)"))


@pytest.mark.rostest
def generate_test_description():
    bridge_node = launch_ros.actions.Node(
        package='ros2_llm_bridge',
        executable='bridge_node',
        output='screen'
    )
    
    return launch.LaunchDescription([
        bridge_node,
        launch_testing.actions.ReadyToTest()
    ]), {'bridge_node': bridge_node}


class TestBridgeNodeCommunication(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node('test_bridge_client')

    def tearDown(self):
        self.node.destroy_node()

    def test_node_starts(self, proc_output):
        # The node should log that it initialized
        proc_output.assertWaitFor('BridgeNode initialized', timeout=5, stream='stdout')
