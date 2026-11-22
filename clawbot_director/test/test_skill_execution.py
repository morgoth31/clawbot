"""Brique 3 : la séquence avance sur la fin réelle des goals.

Domaine 99, aucun robot en mouvement : un faux serveur FollowJointTrajectory tient le rôle du
contrôleur de bras. Ce que ces tests prouvent : le directeur envoie un goal par étape, avance
sur son résultat, échoue quand le goal échoue, annule le goal au délai dépassé, et annule le goal
en cours quand la sécurité coupe la tâche.
"""

import json
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Domaine 99 exigé. Sous pytest en domaine 98 (suite unitaire), le module
# est ignoré au lieu de faire échouer la collecte de tout le dépôt.
pytestmark = pytest.mark.integration
if os.environ.get("ROS_DOMAIN_ID") not in (None, "", "99"):
    pytest.skip(
        f"tests du directeur : ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']} interdit, 99 exigé", allow_module_level=True)
os.environ['ROS_DOMAIN_ID'] = '99'

rclpy = pytest.importorskip('rclpy')
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import String  # noqa: E402

from clawbot_director.director_node import DirectorNode  # noqa: E402
from clawbot_interfaces.srv import DirectorCommand  # noqa: E402
from soutien_actions import FauxBras  # noqa: E402

ACTION_BRAS = '/arm_controller/follow_joint_trajectory'
ETAPE = {'skill': 'arm_move',
         'args': {'positions': [0.0, 0.0, 0.0, 0.0, 0.0], 'duration_s': 0.5}}


@pytest.fixture()
def monde():
    rclpy.init()
    node = DirectorNode()
    executeur = SingleThreadedExecutor()
    executeur.add_node(node)

    sonde = Node('sonde_brique3')
    pub_safety = sonde.create_publisher(String, '/safety/state', 10)
    executeur.add_node(sonde)
    threading.Thread(target=executeur.spin, daemon=True).start()

    bras = FauxBras(mode='succes')
    arret = threading.Event()

    def _alimenter():
        while not arret.is_set():
            pub_safety.publish(String(data='OK'))
            time.sleep(0.05)

    try:
        assert _attendre(lambda: pub_safety.get_subscription_count() > 0, timeout=5.0)
        while node.etat()['safety'] != 'OK' or node.etat()['safety_stale']:
            pub_safety.publish(String(data='OK'))
            time.sleep(0.05)
        # le client d'action doit voir le faux serveur avant le premier goal
        time.sleep(0.5)
        threading.Thread(target=_alimenter, daemon=True).start()
        yield SimpleNamespace(node=node, pub=pub_safety, bras=bras, sonde=sonde)
    finally:
        arret.set()
        bras.fermer()
        executeur.shutdown()
        node.destroy_node()
        sonde.destroy_node()
        rclpy.try_shutdown()


def _attendre(predicate, timeout=3.0, period=0.005):
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        if predicate():
            return True
        time.sleep(period)
    return predicate()


def _appeler(monde, charge, timeout=10.0):
    client = monde.sonde.create_client(DirectorCommand, '/director/command')
    assert client.wait_for_service(timeout_sec=timeout)
    requete = DirectorCommand.Request()
    requete.request_json = json.dumps(charge)
    futur = client.call_async(requete)
    assert _attendre(lambda: futur.done(), timeout=timeout), 'service muet'
    return json.loads(futur.result().response_json)


def _etat(monde):
    return _appeler(monde, {'op': 'get_task'})['task']


def test_sequence_advances_on_each_goal_result(monde):
    demarree = _appeler(monde, {'op': 'start_sequence',
                                'steps': [ETAPE, ETAPE, ETAPE]})
    assert demarree['status'] == 'ACCEPTED'

    assert _attendre(lambda: _etat(monde)['state'] == 'DONE', timeout=10.0), _etat(monde)
    assert monde.bras.recus == 3, f"{monde.bras.recus} goals recus pour 3 etapes"
    fin = _etat(monde)
    assert fin['step'] == fin['steps'] == 3 and fin['reason'] is None


def test_failed_goal_marks_the_task_failed(monde):
    monde.bras.mode = 'echec'
    _appeler(monde, {'op': 'start_sequence', 'steps': [ETAPE, ETAPE]})

    assert _attendre(lambda: _etat(monde)['state'] == 'FAILED', timeout=10.0), _etat(monde)
    etat = _etat(monde)
    assert 'abort' in (etat['reason'] or '').lower()
    assert monde.bras.recus == 1, 'aucune etape ne doit partir apres un echec'


def test_silent_goal_times_out_and_is_cancelled(monde):
    monde.bras.mode = 'silencieux'
    etape = {'skill': 'arm_move',
             'args': {'positions': [0.0] * 5, 'duration_s': 0.5, 'timeout_s': 0.6}}
    _appeler(monde, {'op': 'start_sequence', 'steps': [etape]})

    assert _attendre(lambda: _etat(monde)['state'] == 'FAILED', timeout=5.0), _etat(monde)
    assert _etat(monde)['reason'] == 'TIMEOUT'
    assert _attendre(lambda: monde.bras.annules >= 1, timeout=2.0), 'goal non annule'


def test_safety_stop_cancels_the_active_goal(monde):
    monde.bras.mode = 'silencieux'
    _appeler(monde, {'op': 'start_sequence', 'steps': [ETAPE]})
    assert _attendre(lambda: monde.bras.recus == 1, timeout=3.0)

    monde.pub.publish(String(data='STOP'))
    assert _attendre(lambda: _etat(monde)['state'] == 'CANCELLED_SAFETY', timeout=1.0)
    assert _attendre(lambda: monde.bras.annules >= 1, timeout=2.0), \
        'le goal doit etre annule quand la securite coupe'


def test_cancel_task_cancels_the_active_goal(monde):
    monde.bras.mode = 'silencieux'
    demarree = _appeler(monde, {'op': 'start_sequence', 'steps': [ETAPE]})
    assert _attendre(lambda: monde.bras.recus == 1, timeout=3.0)

    _appeler(monde, {'op': 'cancel_task', 'task_id': demarree['task_id'],
                     'reason': 'operateur'})
    assert _attendre(lambda: _etat(monde)['state'] == 'CANCELLED', timeout=2.0)
    assert _attendre(lambda: monde.bras.annules >= 1, timeout=2.0), 'goal non annule'


def test_unknown_skill_is_refused_before_any_goal(monde):
    reponse = _appeler(monde, {'op': 'start_sequence',
                               'steps': [{'skill': 'teleport', 'args': {}}]})
    assert reponse['status'] == 'INVALID'
    assert 'teleport' in reponse['reason']
    assert monde.bras.recus == 0
