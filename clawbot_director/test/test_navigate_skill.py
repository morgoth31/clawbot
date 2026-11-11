"""Brique 5 : `navigate_to` devient un adaptateur NavigateToPose, pas un refus.

Deux familles de preuves :

  - **logique pure** : l'étape déclarée par S2 se traduit en goal Nav2 exact (cadre, pose, yaw,
    délai), et tout ce qui n'est pas un nom du catalogue est refusé avant envoi ;
  - **domaine 99** : le directeur exécute une séquence de trois waypoints nommés contre un faux
    serveur `NavigateToPose`, avance sur chaque résultat et termine `DONE` — donc le chemin
    « S2 nomme → directeur → action Nav2 » est réellement câblé, indépendamment du fait que le
    robot roule ou non.

Le faux serveur mesure l'écart entre la pose demandée et la pose du catalogue : c'est la même
tolérance que le critère de sortie de la brique (±20 cm), appliquée ici au goal, pas au robot.
"""

from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_director import skills, waypoints  # noqa: E402

CATALOGUE = waypoints.charger()


# ── logique pure : construction du goal ─────────────────────────────────────
def test_navigate_to_produit_un_goal_navigate_to_pose():
    from nav2_msgs.action import NavigateToPose

    plan = skills.construire_plan({"skill": "navigate_to", "args": {"destination": "est"}})
    attendu = CATALOGUE.resoudre("est")

    assert plan.action == "/navigate_to_pose"
    assert plan.type_action is NavigateToPose
    assert plan.goal.pose.header.frame_id == "map"
    assert plan.goal.pose.pose.position.x == pytest.approx(attendu.x)
    assert plan.goal.pose.pose.position.y == pytest.approx(attendu.y)
    # orientation = yaw du catalogue, en quaternion
    q = plan.goal.pose.pose.orientation
    assert q.z == pytest.approx(math.sin(attendu.yaw / 2.0))
    assert q.w == pytest.approx(math.cos(attendu.yaw / 2.0))


def test_navigate_to_refuse_les_coordonnees_libres():
    for args in ({"x": 1.0, "y": 2.0}, {"destination": "est", "x": 1.0},
                 {"destination": {"x": 1.0, "y": 2.0}}, {"pose": [1.0, 2.0]}):
        with pytest.raises(skills.SkillInvalide) as erreur:
            skills.construire_plan({"skill": "navigate_to", "args": args})
        assert "catalogue" in str(erreur.value).lower() or "waypoint" in str(erreur.value).lower()


def test_navigate_to_refuse_un_waypoint_inconnu():
    with pytest.raises(skills.SkillInvalide) as erreur:
        skills.construire_plan({"skill": "navigate_to", "args": {"destination": "cuisine"}})
    assert "cuisine" in str(erreur.value)


def test_navigate_to_delai_par_defaut_et_borne():
    plan = skills.construire_plan({"skill": "navigate_to", "args": {"destination": "centre"}})
    assert plan.timeout_s == pytest.approx(skills.NAVIGATION["timeout_s"])
    with pytest.raises(skills.SkillInvalide):
        skills.construire_plan({"skill": "navigate_to",
                                "args": {"destination": "centre", "timeout_s": 1e6}})


def test_les_autres_skills_restent_indisponibles():
    with pytest.raises(skills.SkillIndisponible):
        skills.construire_plan({"skill": "grasp_object", "args": {"referent": "tasse"}})


# ── domaine 99 : le directeur exécute vraiment les trois waypoints ─────────
if os.environ.get("ROS_DOMAIN_ID") not in (None, "", "99"):
    raise RuntimeError(
        f"tests du directeur : ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']} interdit, 99 exigé")
os.environ["ROS_DOMAIN_ID"] = "99"

rclpy = pytest.importorskip("rclpy")
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import Int32MultiArray, String  # noqa: E402

from clawbot_director.director_node import DirectorNode  # noqa: E402
from clawbot_interfaces.srv import DirectorCommand  # noqa: E402
from soutien_navigation import FauxNavigateur  # noqa: E402

TROIS_ETAPES = [{"skill": "navigate_to", "args": {"destination": nom}}
                for nom in ("ouest", "centre", "est")]


@pytest.fixture()
def monde():
    rclpy.init()
    node = DirectorNode()
    executeur = SingleThreadedExecutor()
    executeur.add_node(node)

    sonde = Node("sonde_brique5")
    pub_safety = sonde.create_publisher(String, "/safety/state", 10)
    # `navigate_to` exige un bras replié : le fixture publie la pose de repos mesurée sur le robot,
    # sinon la précondition refuserait chaque étape et ces tests mesureraient autre chose.
    pub_bras = sonde.create_publisher(Int32MultiArray, "/arm/servo_angles", 10)
    executeur.add_node(sonde)
    threading.Thread(target=executeur.spin, daemon=True).start()

    nav2 = FauxNavigateur(mode="succes")
    arret = threading.Event()

    angles_bras = Int32MultiArray()
    angles_bras.data = [90, 180, 0, 0, 90, 149]

    def _alimenter():
        while not arret.is_set():
            pub_safety.publish(String(data="OK"))
            pub_bras.publish(angles_bras)
            time.sleep(0.05)

    try:
        assert _attendre(lambda: pub_safety.get_subscription_count() > 0, timeout=5.0)
        assert _attendre(lambda: pub_bras.get_subscription_count() > 0, timeout=5.0)
        while node.etat()["safety"] != "OK" or node.etat()["safety_stale"]:
            pub_safety.publish(String(data="OK"))
            time.sleep(0.05)
        time.sleep(0.5)   # découverte DDS du faux serveur avant le premier goal
        threading.Thread(target=_alimenter, daemon=True).start()
        yield SimpleNamespace(node=node, pub=pub_safety, nav2=nav2, sonde=sonde)
    finally:
        arret.set()
        nav2.fermer()
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
    client = monde.sonde.create_client(DirectorCommand, "/director/command")
    assert client.wait_for_service(timeout_sec=timeout)
    requete = DirectorCommand.Request()
    requete.request_json = json.dumps(charge)
    futur = client.call_async(requete)
    assert _attendre(lambda: futur.done(), timeout=timeout), "service muet"
    return json.loads(futur.result().response_json)


def _etat(monde):
    return _appeler(monde, {"op": "get_task"})["task"]


def test_sequence_de_trois_waypoints_nommes(monde):
    demarree = _appeler(monde, {"op": "start_sequence", "steps": TROIS_ETAPES})
    assert demarree["status"] == "ACCEPTED"
    assert demarree["steps"] == 3

    assert _attendre(lambda: _etat(monde)["state"] == "DONE", timeout=20.0), _etat(monde)
    assert monde.nav2.recus == 3, f"{monde.nav2.recus} goals Nav2 recus pour 3 etapes"

    # chaque goal reçu porte la pose du catalogue, au centimètre
    for goal, nom in zip(monde.nav2.goals, ("ouest", "centre", "est")):
        attendu = CATALOGUE.resoudre(nom)
        assert goal.pose.header.frame_id == "map"
        assert math.hypot(goal.pose.pose.position.x - attendu.x,
                          goal.pose.pose.position.y - attendu.y) <= 0.20, nom

    # get_task montre les étapes : c'est le critère de sortie de la brique
    fin = _etat(monde)
    assert fin["step"] == fin["steps"] == 3


def test_waypoint_inconnu_refuse_sans_toucher_nav2(monde):
    reponse = _appeler(monde, {"op": "start_skill", "skill": "navigate_to",
                               "args": {"destination": "cuisine"}})
    assert reponse["status"] == "INVALID"
    assert "cuisine" in reponse["reason"]
    assert monde.nav2.recus == 0


def test_echec_de_nav2_marque_la_tache_en_echec(monde):
    monde.nav2.mode = "echec"
    _appeler(monde, {"op": "start_sequence", "steps": TROIS_ETAPES[:2]})
    assert _attendre(lambda: _etat(monde)["state"] == "FAILED", timeout=15.0), _etat(monde)
    assert monde.nav2.recus == 1, "aucune etape ne doit partir apres un echec de navigation"


def test_arret_de_securite_annule_le_goal_de_navigation(monde):
    monde.nav2.mode = "silencieux"
    _appeler(monde, {"op": "start_sequence", "steps": TROIS_ETAPES[:1]})
    assert _attendre(lambda: monde.nav2.recus == 1, timeout=5.0)

    monde.pub.publish(String(data="STOP"))
    assert _attendre(lambda: _etat(monde)["state"] == "CANCELLED_SAFETY", timeout=1.0)
    assert _attendre(lambda: monde.nav2.annules >= 1, timeout=3.0), "goal Nav2 non annule"
