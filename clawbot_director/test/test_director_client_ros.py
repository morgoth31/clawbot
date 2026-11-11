"""Test du client ponctuel que le pont MCP utilise pour parler au directeur.

Domaine 99 : un DirectorNode tourne dans le processus de test, le client tourne en sous-processus
exactement comme en production (bash + ROS sourcé + JSON sur stdin). Ce test prouve le chemin
complet pont -> service -> directeur, sans YAML et sans robot.
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "clawbot_director"))

if os.environ.get('ROS_DOMAIN_ID') not in (None, '', '99'):
    raise RuntimeError(
        f"tests du directeur : ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']} interdit, 99 exigé")
os.environ['ROS_DOMAIN_ID'] = '99'

rclpy = pytest.importorskip('rclpy')
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import String  # noqa: E402

from clawbot_director.director_node import DirectorNode  # noqa: E402


@pytest.fixture()
def directeur():
    rclpy.init()
    node = DirectorNode()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    sonde = Node('sonde_client')
    pub = sonde.create_publisher(String, '/safety/state', 10)
    executor.add_node(sonde)
    threading.Thread(target=executor.spin, daemon=True).start()
    arret = threading.Event()

    def _alimenter():
        # l'arbitre réel publie à 20 Hz : sans ça, le chien de garde périme la sécurité
        while not arret.is_set():
            pub.publish(String(data='OK'))
            time.sleep(0.05)

    try:
        fin = time.monotonic() + 5.0
        while pub.get_subscription_count() == 0 and time.monotonic() < fin:
            time.sleep(0.02)
        while node.etat()['safety'] != 'OK' or node.etat()['safety_stale']:
            pub.publish(String(data='OK'))
            time.sleep(0.05)
            assert time.monotonic() < fin, 'securite OK jamais etablie'
        threading.Thread(target=_alimenter, daemon=True).start()
        yield node
    finally:
        arret.set()
        executor.shutdown()
        node.destroy_node()
        sonde.destroy_node()
        rclpy.try_shutdown()


def _client(charge: dict, timeout=10.0):
    commande = ("source /opt/ros/humble/setup.bash && "
                f"cd {RACINE} && source install/setup.bash && "
                "exec python3 -m bridge_mcp.director_client")
    env = dict(os.environ, ROS_DOMAIN_ID='99', DIRECTOR_CLIENT_TIMEOUT_S='8')
    proc = subprocess.run(["bash", "-c", commande], input=json.dumps(charge),
                          capture_output=True, text=True, timeout=timeout, env=env)
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None, proc.stderr


def test_client_round_trip_through_the_real_service(directeur):
    code, reponse, err = _client({'op': 'start_skill', 'skill': 'navigate_to',
                                  'args': {'waypoint': "l'atelier"}})
    assert code == 0, err
    assert reponse['status'] == 'ACCEPTED', reponse
    assert reponse['task_id'].startswith('t-')

    code, apres, err = _client({'op': 'get_task', 'task_id': reponse['task_id']})
    assert code == 0, err
    assert apres['status'] == 'FOUND'
    assert apres['task']['skill'] == 'navigate_to'
    # l'apostrophe du référent survit au transport, sans YAML
    assert apres['task']['task_id'] == reponse['task_id']


def test_client_reports_an_absent_service_without_hanging():
    commande = ("source /opt/ros/humble/setup.bash && "
                f"cd {RACINE} && source install/setup.bash && "
                "exec python3 -m bridge_mcp.director_client")
    env = dict(os.environ, ROS_DOMAIN_ID='99', DIRECTOR_CLIENT_TIMEOUT_S='2')
    debut = time.monotonic()
    proc = subprocess.run(["bash", "-c", commande], input=json.dumps({'op': 'get_task'}),
                          capture_output=True, text=True, timeout=30, env=env)
    assert proc.returncode == 3
    assert json.loads(proc.stdout)['status'] == 'ROS_UNAVAILABLE'
    assert time.monotonic() - debut < 15
