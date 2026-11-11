"""Test de contrat du nœud directeur, sans matériel.

Le nœud est lancé dans le processus de test sur un domaine DDS isolé (99) : /safety/state y est
alimenté par une sonde locale, donc aucune interaction avec l'arbitre du domaine 28. Ce que ce
test prouve : une tâche en cours est annulée en moins de 200 ms dès que l'état de sécurité sort
de OK, un OK ne l'annule pas, et /director/state publie l'état interrogeable.
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault('ROS_DOMAIN_ID', '99')

rclpy = pytest.importorskip('rclpy')
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import String  # noqa: E402

from clawbot_director.director import CANCELLED_SAFETY, RUNNING  # noqa: E402
from clawbot_director.director_node import DirectorNode  # noqa: E402


@pytest.fixture()
def stack():
    rclpy.init()
    node = DirectorNode()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)

    probe = Node('probe_director')
    pub_safety = probe.create_publisher(String, '/safety/state', 10)
    published = []
    probe.create_subscription(String, '/director/state',
                              lambda m: published.append((time.time(), json.loads(m.data))), 10)
    executor.add_node(probe)

    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    time.sleep(1.0)   # découverte DDS avant le premier message
    try:
        yield node, pub_safety, published
    finally:
        executor.shutdown()
        node.destroy_node()
        probe.destroy_node()
        rclpy.shutdown()


def _wait_for(predicate, timeout=2.0, period=0.005):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(period)
    return predicate()


def test_stop_cancels_running_task_within_200ms(stack):
    node, pub_safety, _ = stack
    demarree = node.director.start('navigate_to', {'waypoint': 'cuisine'})
    assert demarree['status'] == 'ACCEPTED'
    assert node.director.state()['state'] == RUNNING

    t0 = time.time()
    pub_safety.publish(String(data='STOP'))
    assert _wait_for(lambda: node.director.state()['state'] == CANCELLED_SAFETY, timeout=1.0)
    ecoule = time.time() - t0

    assert ecoule < 0.2, f'annulation en {ecoule * 1000:.0f} ms, 200 ms exigés'
    etat = node.director.state()
    assert etat['task_id'] == demarree['task_id']


def test_ok_state_does_not_cancel_the_task(stack):
    node, pub_safety, _ = stack
    node.director.start('navigate_to', {'waypoint': 'cuisine'})

    pub_safety.publish(String(data='OK'))
    time.sleep(0.3)

    assert node.director.state()['state'] == RUNNING


def test_director_state_is_published_even_without_any_change(stack):
    # un abonné tardif (S2, supervision) doit voir l'état sans attendre un événement
    node, _, published = stack
    assert _wait_for(lambda: len(published) > 0, timeout=1.5), \
        'aucune publication de /director/state sans changement d etat'
    assert published[-1][1]['state'] == 'IDLE'


def test_director_state_is_published_and_reports_the_cancellation(stack):
    node, pub_safety, published = stack
    demarree = node.director.start('navigate_to', {'waypoint': 'cuisine'})
    assert _wait_for(lambda: any(m.get('task_id') == demarree['task_id'] for _, m in published))

    pub_safety.publish(String(data='HOLD'))
    assert _wait_for(lambda: any(m.get('state') == CANCELLED_SAFETY for _, m in published))
    dernier = published[-1][1]
    assert dernier['task_id'] == demarree['task_id']
    assert dernier['safety'] == 'HOLD'
