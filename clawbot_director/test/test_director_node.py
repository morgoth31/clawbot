"""Test de contrat du nœud directeur, sans matériel.

Le nœud est lancé dans le processus de test sur un domaine DDS isolé (99) : /safety/state y est
alimenté par une sonde locale, donc aucune interaction avec l'arbitre du domaine 28. Ce que ces
tests prouvent : une porte à l'entrée (pas de tâche sans OK frais), une annulation en moins de
200 ms quand l'état sort de OK, un chien de garde quand l'arbitre se tait, et un état publié
daté, stable et interrogeable.

La grandeur mesurée est le passage de la tâche à CANCELLED_SAFETY, pas l'arrêt physique du
robot : /safety/hold est l'affaire de l'arbitre, goal_cancel celle de la brique 3.
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ENV-01 du dépôt : jamais 28 pendant un test, et jamais silencieusement.
if os.environ.get('ROS_DOMAIN_ID') not in (None, '', '99'):
    raise RuntimeError(
        f"tests du directeur : ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']} interdit, 99 exigé")
os.environ['ROS_DOMAIN_ID'] = '99'

rclpy = pytest.importorskip('rclpy')
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import String  # noqa: E402

from clawbot_director.director import (  # noqa: E402
    CANCELLED_SAFETY, PRECONDITION_FAILED, RUNNING,
)
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
                              lambda m: published.append((time.monotonic(), json.loads(m.data))),
                              10)
    executor.add_node(probe)

    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        assert _attendre(lambda: pub_safety.get_subscription_count() > 0, timeout=5.0), \
            'appariement DDS non etabli avant le test'
        assert _attendre(lambda: len(published) > 0, timeout=2.0), '/director/state muet'
        yield node, pub_safety, published
    finally:
        executor.shutdown()
        node.destroy_node()
        probe.destroy_node()
        rclpy.try_shutdown()


def _attendre(predicate, timeout=2.0, period=0.002):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(period)
    return predicate()


def _publier_jusqua(pub_safety, valeur, predicate, timeout=3.0):
    """Publie jusqu'à ce que l'effet soit observé (une publication unique peut se perdre)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pub_safety.publish(String(data=valeur))
        if _attendre(predicate, timeout=0.15):
            return True
    return predicate()


def _securite_ok(node, pub_safety):
    assert _publier_jusqua(pub_safety, 'OK',
                           lambda: node.etat()['safety'] == 'OK'
                           and not node.etat()['safety_stale']), 'OK jamais recu par le noeud'


def test_stop_cancels_running_task_within_200ms(stack):
    node, pub_safety, _ = stack
    _securite_ok(node, pub_safety)
    demarree = node.start('navigate_to', {'waypoint': 'cuisine'})
    assert demarree['status'] == 'ACCEPTED'
    assert node.director.state()['state'] == RUNNING

    t0 = time.perf_counter()
    pub_safety.publish(String(data='STOP'))
    assert _attendre(lambda: node.director.state()['state'] == CANCELLED_SAFETY, timeout=1.0)
    ecoule = time.perf_counter() - t0

    assert ecoule < 0.2, f'annulation en {ecoule * 1000:.0f} ms, 200 ms exigés'
    assert node.director.state()['task_id'] == demarree['task_id']


def test_ok_state_does_not_cancel_the_task(stack):
    node, pub_safety, published = stack
    _securite_ok(node, pub_safety)
    node.start('navigate_to', {'waypoint': 'cuisine'})

    pub_safety.publish(String(data='OK'))
    time.sleep(0.3)

    assert node.director.state()['state'] == RUNNING
    # discrimine « OK correctement ignoré » de « sécurité pas écoutée du tout »
    assert any(m['safety'] == 'OK' for _, m in published)


def test_director_state_is_published_even_without_any_change(stack):
    # un abonné tardif (S2, supervision) doit voir l'état sans attendre un événement
    node, _, published = stack
    assert _attendre(lambda: len(published) > 0, timeout=1.5)
    etat = published[-1][1]
    assert etat['state'] == 'IDLE'
    for cle in ('task_id', 'skill', 'step', 'steps', 'elapsed_s', 'started_at', 'reason',
                'safety', 'safety_age_s', 'safety_stale', 'published_at'):
        assert cle in etat, f'champ {cle} absent de /director/state'
    assert etat['task_id'] is None and etat['reason'] is None
    assert etat['published_at'] > 0


def test_director_state_reports_the_cancellation(stack):
    node, pub_safety, published = stack
    _securite_ok(node, pub_safety)
    demarree = node.start('navigate_to', {'waypoint': 'cuisine'})

    assert _publier_jusqua(pub_safety, 'HOLD',
                           lambda: any(m['state'] == CANCELLED_SAFETY for _, m in published))
    dernier = [m for _, m in published if m['state'] == CANCELLED_SAFETY][-1]
    assert dernier['task_id'] == demarree['task_id']
    assert dernier['safety'] == 'HOLD'
    assert dernier['reason'] == 'safety'


def test_task_is_refused_when_safety_is_already_in_default(stack):
    node, pub_safety, _ = stack
    _publier_jusqua(pub_safety, 'STOP', lambda: node.etat()['safety'] == 'STOP')

    refus = node.start('navigate_to', {'waypoint': 'cuisine'})
    assert refus['status'] == PRECONDITION_FAILED
    assert 'STOP' in refus['reason']
    assert node.director.state()['state'] == 'IDLE', 'aucune tache ne doit naitre sous STOP'


def test_task_is_refused_when_safety_never_spoke(stack):
    # arbitre mort ou pas encore démarré : le silence n'est pas un feu vert
    node, _, _ = stack
    assert node.etat()['safety'] is None
    refus = node.start('navigate_to', {'waypoint': 'cuisine'})
    assert refus['status'] == PRECONDITION_FAILED
    assert 'securite' in refus['reason']


def test_silent_safety_feed_cancels_the_task_via_watchdog(stack):
    node, pub_safety, published = stack
    _securite_ok(node, pub_safety)
    node.start('navigate_to', {'waypoint': 'cuisine'})

    # plus aucun message : l'arbitre est muet, la dernière valeur connue est périmée
    assert _attendre(lambda: node.director.state()['state'] == CANCELLED_SAFETY, timeout=2.5)
    assert node.director.state()['reason'] == 'safety_stale'
    assert _attendre(lambda: any(m['safety_stale'] for _, m in published), timeout=0.5)


def test_repeated_stop_does_not_duplicate_the_cancellation(stack):
    node, pub_safety, _ = stack
    _securite_ok(node, pub_safety)
    node.start('navigate_to', {'waypoint': 'cuisine'})

    for _ in range(20):
        pub_safety.publish(String(data='STOP'))
        time.sleep(0.01)
    assert _attendre(lambda: node.director.state()['state'] == CANCELLED_SAFETY, timeout=1.0)

    annulations = [h for h in node.director._task.history if h.get('reason') == 'safety']
    assert len(annulations) == 1, f'{len(annulations)} annulations journalisees pour un seul STOP'
