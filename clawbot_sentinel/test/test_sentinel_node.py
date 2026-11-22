"""Nœud sentinel : domaine 99, capteurs et directeur simulés.

Ce que ces tests prouvent : la personne n'est engagée qu'avec confiance et distance suffisantes
et deux observations consécutives ; un mot d'arrêt coupe sans S2 ; « oui » n'est consommé qu'en
WAITING_CONFIRMATION ; une fin de tâche réveille S2 une fois, pas cinq fois par seconde.
"""

import json
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "clawbot_sentinel"))

# Domaine 99 exigé. Sous pytest en domaine 98 (suite unitaire), le module
# est ignoré au lieu de faire échouer la collecte de tout le dépôt.
pytestmark = pytest.mark.integration
if os.environ.get("ROS_DOMAIN_ID") not in (None, "", "99"):
    pytest.skip(
        f"tests du sentinel : ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']} interdit, 99 exigé", allow_module_level=True)
os.environ['ROS_DOMAIN_ID'] = '99'

rclpy = pytest.importorskip('rclpy')
from geometry_msgs.msg import Twist  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy  # noqa: E402
from std_msgs.msg import Bool, String  # noqa: E402

from clawbot_interfaces.srv import DirectorCommand  # noqa: E402
from clawbot_sentinel.attention import ENGAGED, IDLE  # noqa: E402
from clawbot_sentinel.sentinel_node import SentinelNode  # noqa: E402


class FauxDirecteur:
    """Serveur /director/command : enregistre les requêtes, répond ce qu'on lui dit."""

    def __init__(self, node):
        self.requetes = []
        self.reponse = {"status": "CANCELLED", "task_id": "t-abc", "step": 0}
        self._srv = node.create_service(DirectorCommand, '/director/command', self._traiter)

    def _traiter(self, requete, reponse):
        self.requetes.append(json.loads(requete.request_json))
        reponse.response_json = json.dumps(self.reponse)
        return reponse


@pytest.fixture()
def monde():
    if not rclpy.ok():        # contexte partagé par la session de test
        rclpy.init()
    observations = SimpleNamespace(detections=[], distance=None)
    reveils = []

    node = SentinelNode(sondeur=lambda: list(observations.detections),
                        distanceur=lambda _bbox: observations.distance,
                        declencheur=lambda evenement: reveils.append(evenement) or True)

    executeur = MultiThreadedExecutor(num_threads=3)
    executeur.add_node(node)

    sonde = Node('sonde_sentinel')
    executeur.add_node(sonde)
    faux = FauxDirecteur(sonde)
    pub_transcript = sonde.create_publisher(String, '/sentinel/transcript', 10)
    pub_directeur = sonde.create_publisher(String, '/director/state', 10)
    vitesses = []          # doit rester vide : la sentinelle n'édite plus la vitesse
    sonde.create_subscription(Twist, '/cmd_vel', lambda m: vitesses.append(m), 50)
    estops = []
    sonde.create_subscription(
        Bool, '/safety/estop', lambda m: estops.append(m),
        QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                   durability=DurabilityPolicy.TRANSIENT_LOCAL))
    etats = []
    sonde.create_subscription(String, '/sentinel/state',
                              lambda m: etats.append(json.loads(m.data)), 10)
    threading.Thread(target=executeur.spin, daemon=True).start()
    try:
        assert _attendre(lambda: pub_transcript.get_subscription_count() > 0, timeout=5.0)
        yield SimpleNamespace(node=node, observations=observations, reveils=reveils,
                              directeur=faux, pub_transcript=pub_transcript,
                              pub_directeur=pub_directeur, vitesses=vitesses,
                              estops=estops, etats=etats)
    finally:
        executeur.shutdown()
        node.destroy_node()
        sonde.destroy_node()
        # contexte partagé : ne pas l'éteindre entre deux fichiers


def _attendre(predicate, timeout=3.0, period=0.01):
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        if predicate():
            return True
        time.sleep(period)
    return predicate()


def _personne(confiance=0.9, bbox=(10, 10, 50, 50)):
    return {'label': 'person', 'confidence': confiance,
            'bbox': list(bbox), 'distance_m': None}


def test_une_personne_proche_et_confirmee_engage_et_reveille(monde):
    monde.observations.detections = [_personne()]
    monde.observations.distance = 1.5

    assert _attendre(lambda: monde.node.attention.etat == ENGAGED, timeout=4.0), \
        monde.etats[-3:]
    assert [e['source'] for e in monde.reveils] == ['VISUAL_PERSON']
    assert monde.reveils[0]['event_data']['distance_m'] == pytest.approx(1.5)


def test_une_personne_lointaine_n_engage_pas(monde):
    monde.observations.detections = [_personne()]
    monde.observations.distance = 5.0

    time.sleep(2.5)
    assert monde.node.attention.etat == IDLE
    assert monde.reveils == []


def test_un_mot_d_arret_annule_la_tache_et_pose_l_estop(monde):
    """Mot d'arrêt : la tâche est annulée et l'e-stop est posé (REQ-SAFETY-016).

    Avant P04 la sentinelle publiait un Twist nul sur /cmd_vel : c'était une
    troisième source de vitesse, et un zéro n'est pas un verrou — la consigne
    suivante repartait. Désormais elle publie Bool(True) sur /safety/estop.
    """
    monde.pub_transcript.publish(String(data='Arrête-toi !'))

    assert _attendre(lambda: monde.directeur.requetes, timeout=3.0)
    requete = monde.directeur.requetes[0]
    assert requete['op'] == 'cancel_task'
    assert requete['reason'] == 'voix_arret'
    assert _attendre(lambda: monde.estops, timeout=2.0), 'aucun e-stop publie'
    assert monde.estops[-1].data is True
    assert monde.vitesses == [], 'la sentinelle ne doit plus rien publier sur /cmd_vel'


def test_oui_hors_attente_de_confirmation_n_est_pas_consomme(monde):
    monde.pub_directeur.publish(String(data=json.dumps({'state': 'RUNNING', 'task_id': 't-1'})))
    time.sleep(0.3)
    monde.pub_transcript.publish(String(data='oui'))
    time.sleep(0.6)

    assert monde.directeur.requetes == []


def test_oui_en_attente_de_confirmation_confirme(monde):
    monde.pub_directeur.publish(String(data=json.dumps(
        {'state': 'WAITING_CONFIRMATION', 'task_id': 't-1'})))
    time.sleep(0.3)
    monde.faux = monde.directeur
    monde.directeur.reponse = {'status': 'RUNNING', 'task_id': 't-1'}
    monde.pub_transcript.publish(String(data='oui'))
    time.sleep(0.8)

    assert [r['op'] for r in monde.directeur.requetes] == ['confirm']
    assert monde.directeur.requetes[0]['accepte'] is True


def test_fin_de_tache_reveille_une_fois_malgre_la_publication_a_5_hz(monde):
    fin = json.dumps({'state': 'DONE', 'task_id': 't-42', 'reason': None})
    # 3 s de publications : au-dela de l'anti-rebond de 2 s, seule la memoire du task_id
    # empeche un second reveil pour la meme fin de tache
    fin_emission = time.monotonic() + 3.0
    while time.monotonic() < fin_emission:
        monde.pub_directeur.publish(String(data=fin))
        time.sleep(0.2)

    reveils = [e for e in monde.reveils if e['source'] == 'TASK_TERMINAL']
    assert len(reveils) == 1, f"{len(reveils)} reveils pour une seule fin de tache"
    assert reveils[0]['event_data']['task_id'] == 't-42'
    assert reveils[0]['event_data']['state'] == 'DONE'
