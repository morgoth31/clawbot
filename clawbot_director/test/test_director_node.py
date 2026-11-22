"""Test de contrat du nœud directeur, sans matériel.

Le nœud est lancé dans le processus de test sur un domaine DDS isolé (99) : /safety/state y est
alimenté par une sonde locale, donc aucune interaction avec l'arbitre du domaine 28. Ce que ces
tests prouvent : une porte à l'entrée (pas de tâche sans OK frais), une annulation en moins de
200 ms quand l'état sort de OK, un chien de garde quand l'arbitre se tait, un service
/director/command qui n'accepte que des opérations connues, et un état publié daté et stable.

La grandeur mesurée est le passage de la tâche à CANCELLED_SAFETY, pas l'arrêt physique du
robot : /safety/hold est l'affaire de l'arbitre, goal_cancel celle de la brique 3.
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

# ENV-01 du dépôt : jamais 28 pendant un test, et jamais silencieusement.
# Domaine 99 exigé. Sous pytest en domaine 98 (suite unitaire), le module
# est ignoré au lieu de faire échouer la collecte de tout le dépôt.
pytestmark = pytest.mark.integration
if os.environ.get("ROS_DOMAIN_ID") not in (None, "", "99"):
    pytest.skip(
        f"tests du directeur : ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']} interdit, 99 exigé", allow_module_level=True)
os.environ['ROS_DOMAIN_ID'] = '99'

rclpy = pytest.importorskip('rclpy')
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import Int32MultiArray, String  # noqa: E402

from clawbot_director.director import (  # noqa: E402
    CANCELLED_SAFETY, PRECONDITION_FAILED, RUNNING,
)
from clawbot_director.director_node import DirectorNode  # noqa: E402
from soutien_actions import FauxBras  # noqa: E402
from clawbot_interfaces.srv import DirectorCommand  # noqa: E402


@pytest.fixture()
def stack():
    rclpy.init()
    node = DirectorNode()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)

    probe = Node('probe_director')
    pub_safety = probe.create_publisher(String, '/safety/state', 10)
    # `navigate_to` exige un bras replié mesuré : sans ce flux, la précondition refuse la tâche et
    # ces tests ne mesureraient plus l'annulation mais le refus.
    pub_bras = probe.create_publisher(Int32MultiArray, '/arm/servo_angles', 10)
    published = []
    probe.create_subscription(String, '/director/state',
                              lambda m: published.append((time.monotonic(), json.loads(m.data))),
                              10)
    executor.add_node(probe)

    bras = FauxBras(mode='silencieux')
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    angles = Int32MultiArray()
    angles.data = [90, 180, 0, 0, 90, 149]
    arret = threading.Event()

    def _alimenter_bras():
        while not arret.is_set():
            pub_bras.publish(angles)
            time.sleep(0.05)

    threading.Thread(target=_alimenter_bras, daemon=True).start()

    try:
        assert _attendre(lambda: pub_safety.get_subscription_count() > 0, timeout=5.0), \
            'appariement DDS non établi avant le test'
        assert _attendre(lambda: pub_bras.get_subscription_count() > 0, timeout=5.0), \
            'flux des angles de bras non apparié'
        assert _attendre(lambda: node.etat()['arm_folded'], timeout=3.0), \
            'le directeur doit voir le bras replié avant de démarrer une tâche'
        assert _attendre(lambda: len(published) > 0, timeout=2.0), '/director/state muet'
        yield SimpleNamespace(node=node, pub_safety=pub_safety, published=published, probe=probe)
    finally:
        arret.set()
        bras.fermer()
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


def _appeler(pile, charge, timeout=5.0):
    """Appel du service /director/command, comme le fera le pont MCP."""
    client = pile.probe.create_client(DirectorCommand, '/director/command')
    assert client.wait_for_service(timeout_sec=timeout), 'service /director/command absent'
    requete = DirectorCommand.Request()
    requete.request_json = json.dumps(charge)
    futur = client.call_async(requete)
    assert _attendre(lambda: futur.done(), timeout=timeout), 'reponse du service jamais arrivee'
    return json.loads(futur.result().response_json)


def test_stop_cancels_running_task_within_200ms(stack):
    _securite_ok(stack.node, stack.pub_safety)
    demarree = stack.node.director.start('navigate_to', {'waypoint': 'cuisine'})
    assert demarree['status'] == 'ACCEPTED'
    assert stack.node.director.state()['state'] == RUNNING

    t0 = time.perf_counter()
    stack.pub_safety.publish(String(data='STOP'))
    assert _attendre(lambda: stack.node.director.state()['state'] == CANCELLED_SAFETY, timeout=1.0)
    ecoule = time.perf_counter() - t0

    assert ecoule < 0.2, f'annulation en {ecoule * 1000:.0f} ms, 200 ms exigés'
    assert stack.node.director.state()['task_id'] == demarree['task_id']


def test_ok_state_does_not_cancel_the_task(stack):
    _securite_ok(stack.node, stack.pub_safety)
    stack.node.director.start('navigate_to', {'waypoint': 'cuisine'})

    stack.pub_safety.publish(String(data='OK'))
    time.sleep(0.3)

    assert stack.node.director.state()['state'] == RUNNING
    # discrimine « OK correctement ignoré » de « sécurité pas écoutée du tout »
    assert any(m['safety'] == 'OK' for _, m in stack.published)


def test_director_state_is_published_even_without_any_change(stack):
    # un abonné tardif (S2, supervision) doit voir l'état sans attendre un événement
    assert _attendre(lambda: len(stack.published) > 0, timeout=1.5)
    etat = stack.published[-1][1]
    assert etat['state'] == 'IDLE'
    for cle in ('task_id', 'skill', 'step', 'steps', 'elapsed_s', 'started_at', 'reason',
                'safety', 'safety_age_s', 'safety_stale', 'published_at'):
        assert cle in etat, f'champ {cle} absent de /director/state'
    assert etat['task_id'] is None and etat['reason'] is None
    assert etat['published_at'] > 0


def test_director_state_reports_the_cancellation(stack):
    _securite_ok(stack.node, stack.pub_safety)
    demarree = stack.node.director.start('navigate_to', {'waypoint': 'cuisine'})

    assert _publier_jusqua(stack.pub_safety, 'HOLD',
                           lambda: any(m['state'] == CANCELLED_SAFETY for _, m in stack.published))
    dernier = [m for _, m in stack.published if m['state'] == CANCELLED_SAFETY][-1]
    assert dernier['task_id'] == demarree['task_id']
    assert dernier['safety'] == 'HOLD'
    assert dernier['reason'] == 'safety'


def test_task_is_refused_when_safety_is_already_in_default(stack):
    _publier_jusqua(stack.pub_safety, 'STOP', lambda: stack.node.etat()['safety'] == 'STOP')

    refus = stack.node.start('navigate_to', {'waypoint': 'cuisine'})
    assert refus['status'] == PRECONDITION_FAILED
    assert 'STOP' in refus['reason']
    assert stack.node.director.state()['state'] == 'IDLE', 'aucune tache ne doit naitre sous STOP'


def test_task_is_refused_when_safety_never_spoke(stack):
    # arbitre mort ou pas encore démarré : le silence n'est pas un feu vert
    assert stack.node.etat()['safety'] is None
    refus = stack.node.start('navigate_to', {'waypoint': 'cuisine'})
    assert refus['status'] == PRECONDITION_FAILED
    assert 'securite' in refus['reason']


def test_silent_safety_feed_cancels_the_task_via_watchdog(stack):
    _securite_ok(stack.node, stack.pub_safety)
    stack.node.director.start('navigate_to', {'waypoint': 'cuisine'})

    # plus aucun message : l'arbitre est muet, la dernière valeur connue est périmée
    assert _attendre(lambda: stack.node.director.state()['state'] == CANCELLED_SAFETY,
                     timeout=2.5)
    assert stack.node.director.state()['reason'] == 'safety_stale'
    assert _attendre(lambda: any(m['safety_stale'] for _, m in stack.published), timeout=0.5)


def test_repeated_stop_does_not_duplicate_the_cancellation(stack):
    _securite_ok(stack.node, stack.pub_safety)
    stack.node.director.start('navigate_to', {'waypoint': 'cuisine'})

    for _ in range(20):
        stack.pub_safety.publish(String(data='STOP'))
        time.sleep(0.01)
    assert _attendre(lambda: stack.node.director.state()['state'] == CANCELLED_SAFETY, timeout=1.0)

    annulations = [h for h in stack.node.director._task.history if h.get('reason') == 'safety']
    assert len(annulations) == 1, f'{len(annulations)} annulations journalisees pour un seul STOP'


# ── surface de service : ce que le pont MCP appellera ────────────────────────
def test_service_start_skill_accepts_and_the_task_is_visible(stack):
    _securite_ok(stack.node, stack.pub_safety)

    reponse = _appeler(stack, {'op': 'start_skill', 'skill': 'arm_move',
                               'args': {'positions': [0.0] * 5, 'duration_s': 0.5}})
    assert reponse['status'] == 'ACCEPTED'
    assert reponse['task_id'].startswith('t-')

    etat = _appeler(stack, {'op': 'get_task'})
    assert etat['status'] == 'FOUND'
    assert etat['task']['task_id'] == reponse['task_id']
    assert etat['task']['state'] == RUNNING
    assert etat['task']['skill'] == 'arm_move'


def test_service_second_start_receives_busy_with_the_current_task_id(stack):
    _securite_ok(stack.node, stack.pub_safety)
    premier = _appeler(stack, {'op': 'start_skill', 'skill': 'arm_move',
                               'args': {'positions': [0.0] * 5, 'duration_s': 0.5}})

    second = _appeler(stack, {'op': 'start_skill', 'skill': 'grasp_object', 'args': {}})
    assert second['status'] == 'BUSY'
    assert second['task_id'] == premier['task_id']


def test_service_cancel_task_cancels_and_stays_consultable(stack):
    _securite_ok(stack.node, stack.pub_safety)
    demarree = _appeler(stack, {'op': 'start_skill', 'skill': 'arm_move',
                               'args': {'positions': [0.0] * 5, 'duration_s': 0.5}})

    annulee = _appeler(stack, {'op': 'cancel_task', 'task_id': demarree['task_id'],
                               'reason': 'operateur'})
    assert annulee['status'] == 'CANCELLED'

    apres = _appeler(stack, {'op': 'get_task', 'task_id': demarree['task_id']})
    assert apres['status'] == 'FOUND'
    assert apres['task']['state'] == 'CANCELLED'


def test_service_get_task_on_unknown_id_says_so(stack):
    reponse = _appeler(stack, {'op': 'get_task', 'task_id': 't-inexistant'})
    assert reponse['status'] == 'UNKNOWN_TASK'


def test_service_confirm_resume_seulement_en_attente_de_confirmation(stack):
    _securite_ok(stack.node, stack.pub_safety)
    demarree = _appeler(stack, {'op': 'start_skill', 'skill': 'arm_move',
                                'args': {'positions': [0.0] * 5, 'duration_s': 0.5}})
    assert demarree['status'] == 'ACCEPTED'

    hors_attente = _appeler(stack, {'op': 'confirm', 'accepte': True})
    assert hors_attente['status'] == 'NO_TASK'

    stack.node.director.ask_confirmation()
    confirme = _appeler(stack, {'op': 'confirm', 'accepte': True})
    assert confirme['status'] == 'RUNNING'
    assert stack.node.director.state()['task_id'] == demarree['task_id']


def test_service_start_is_gated_by_safety_like_the_python_api(stack):
    _publier_jusqua(stack.pub_safety, 'STOP', lambda: stack.node.etat()['safety'] == 'STOP')

    reponse = _appeler(stack, {'op': 'start_skill', 'skill': 'arm_move',
                               'args': {'positions': [0.0] * 5, 'duration_s': 0.5}})
    assert reponse['status'] == PRECONDITION_FAILED
    assert 'STOP' in reponse['reason']


def test_service_rejects_an_unknown_operation_without_side_effect(stack):
    reponse = _appeler(stack, {'op': 'rm_rf'})
    assert reponse['status'] == 'INVALID'
    assert stack.node.director.state()['state'] == 'IDLE'


def test_service_rejects_malformed_json(stack):
    client = stack.probe.create_client(DirectorCommand, '/director/command')
    assert client.wait_for_service(timeout_sec=5.0)
    requete = DirectorCommand.Request()
    requete.request_json = '{"op": '
    futur = client.call_async(requete)
    assert _attendre(lambda: futur.done(), timeout=5.0)
    reponse = json.loads(futur.result().response_json)
    assert reponse['status'] == 'INVALID'
