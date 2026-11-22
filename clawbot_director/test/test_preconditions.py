"""Précondition « bras replié » avant tout skill qui déplace la base (spec §6 règle 3).

Deux familles de preuves :

  - **logique pure** : l'enveloppe est lue dans un fichier validé, le refus nomme le servo fautif,
    et un bras inconnu (jamais reçu, ou périmé) est refusé — le silence n'est pas un feu vert ;
  - **domaine 99** : le directeur refuse réellement un `navigate_to` bras en extension, l'accepte
    bras dans l'enveloppe, et continue d'accepter `arm_move` — sans quoi le bras ne pourrait plus
    être replié par le directeur lui-même.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_director import preconditions as regles  # noqa: E402

ENVELOPPE = regles.charger()


# ── logique pure ─────────────────────────────────────────────────────────────
def test_l_enveloppe_par_defaut_se_charge():
    assert ENVELOPPE.arm.source == "/arm/servo_angles"
    assert ENVELOPPE.arm.joints == (1, 2, 3, 4, 5)
    assert ENVELOPPE.exige_bras_replie("navigate_to")
    assert not ENVELOPPE.exige_bras_replie("arm_move")
    # l'enveloppe est validée par l'opérateur, et c'est écrit dans le fichier
    assert ENVELOPPE.arm.valide_par_operateur is True


def test_un_bras_dans_l_enveloppe_est_accepte():
    angles = list(ENVELOPPE.arm.reference_deg) + [149]
    ok, raison = regles.verifier("navigate_to", angles, 0.1, ENVELOPPE)
    assert ok, raison


def test_un_bras_hors_enveloppe_refuse_en_nommant_le_servo():
    angles = [90, 120, 0, 0, 90, 149]         # servo 2 en extension, hors de la pose de repos
    ok, raison = regles.verifier("navigate_to", angles, 0.1, ENVELOPPE)
    assert not ok
    assert "servo 2" in raison and "120" in raison


def test_des_angles_perimes_sont_refuses():
    angles = list(ENVELOPPE.arm.reference_deg) + [149]
    ok, raison = regles.verifier("navigate_to", angles, ENVELOPPE.arm.max_age_s + 0.5, ENVELOPPE)
    assert not ok
    assert "perimes" in raison


def test_des_angles_jamais_recus_sont_refuses():
    ok, raison = regles.verifier("navigate_to", None, None, ENVELOPPE)
    assert not ok
    assert "aucun message" in raison


def test_des_angles_incomplets_sont_refuses():
    ok, raison = regles.verifier("navigate_to", [76, 97], 0.1, ENVELOPPE)
    assert not ok
    assert "incomplets" in raison


def test_un_skill_sans_deplacement_n_est_pas_soumis_a_l_enveloppe():
    angles_hors_bande = [76, 170, 20, 20, 20, 149]
    for skill in ("arm_move", "grip_set"):
        ok, raison = regles.verifier(skill, angles_hors_bande, 0.1, ENVELOPPE)
        assert ok, f"{skill} doit rester executable pour replier le bras : {raison}"


def _ecrire(tmp_path, contenu: str) -> Path:
    chemin = tmp_path / "preconditions.yaml"
    chemin.write_text(contenu)
    return chemin


VALIDE = """arm:
  source: /arm/servo_angles
  max_age_s: 1.0
  joints: [1, 2, 3, 4, 5]
  reference_deg: [76, 97, 90, 90, 90]
  tolerance_deg: [10, 10, 10, 10, 10]
skills_exigeant_bras_replie: [navigate_to]
"""


@pytest.mark.parametrize("contenu, motif", [
    ("skills_exigeant_bras_replie: [navigate_to]\n", "arm"),
    (VALIDE.replace("[1, 2, 3, 4, 5]", "[1, 2, 3]"), "valeurs"),
    (VALIDE.replace("[10, 10, 10, 10, 10]", "[10, 0, 10, 10, 10]"), "positif"),
    (VALIDE.replace("[1, 2, 3, 4, 5]", "[1, 2, 3, 4, 9]"), "servo"),
    (VALIDE.replace("skills_exigeant_bras_replie: [navigate_to]", "skills_exigeant_bras_replie: []"),
     "liste non vide"),
    (VALIDE.replace("skills_exigeant_bras_replie: [navigate_to]\n",
                    "skills_exigeant_bras_replie: [navigate_to]\ncouleur: rouge\n"), "inconnue"),
    (VALIDE.replace("  tolerance_deg: [10, 10, 10, 10, 10]\n",
                    "  tolerance_deg: [10, 10, 10, 10, 10]\n  couleur: rouge\n"), "inconnue"),
    (VALIDE.replace("max_age_s: 1.0", "max_age_s: 99.0"), "bornes"),
])
def test_une_configuration_malformee_est_refusee(tmp_path, contenu, motif):
    with pytest.raises(regles.PreconditionsInvalides) as erreur:
        regles.charger(_ecrire(tmp_path, contenu))
    assert motif in str(erreur.value).lower(), str(erreur.value)


# ── domaine 99 : le directeur applique la précondition ─────────────────────
# Domaine 99 exigé. Sous pytest en domaine 98 (suite unitaire), le module
# est ignoré au lieu de faire échouer la collecte de tout le dépôt.
pytestmark = pytest.mark.integration
if os.environ.get("ROS_DOMAIN_ID") not in (None, "", "99"):
    pytest.skip(
        f"tests du directeur : ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']} interdit, 99 exigé", allow_module_level=True)
os.environ["ROS_DOMAIN_ID"] = "99"

rclpy = pytest.importorskip("rclpy")
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import Int32MultiArray, String  # noqa: E402

from clawbot_director.director_node import DirectorNode  # noqa: E402
from clawbot_interfaces.srv import DirectorCommand  # noqa: E402
from soutien_actions import FauxBras  # noqa: E402
from soutien_navigation import FauxNavigateur  # noqa: E402

ANGLES_REPLIE = [90, 180, 0, 0, 90, 149]      # pose de repos validée par l'opérateur
ANGLES_EXTENSION = [90, 120, 0, 0, 90, 149]


@pytest.fixture()
def monde():
    node = DirectorNode()        # contexte rclpy fourni par conftest.py
    executeur = SingleThreadedExecutor()
    executeur.add_node(node)
    sonde = Node("sonde_preconditions")
    pub_safety = sonde.create_publisher(String, "/safety/state", 10)
    pub_bras = sonde.create_publisher(Int32MultiArray, "/arm/servo_angles", 10)
    executeur.add_node(sonde)
    threading.Thread(target=executeur.spin, daemon=True).start()

    nav2 = FauxNavigateur(mode="succes")
    bras = FauxBras(mode="succes")
    arret = threading.Event()

    def _alimenter():
        while not arret.is_set():
            pub_safety.publish(String(data="OK"))
            time.sleep(0.05)

    try:
        assert _attendre(lambda: pub_safety.get_subscription_count() > 0, timeout=5.0)
        assert _attendre(lambda: pub_bras.get_subscription_count() > 0, timeout=5.0)
        while node.etat()["safety"] != "OK" or node.etat()["safety_stale"]:
            pub_safety.publish(String(data="OK"))
            time.sleep(0.05)
        threading.Thread(target=_alimenter, daemon=True).start()
        yield SimpleNamespace(node=node, pub=pub_safety, pub_bras=pub_bras,
                              nav2=nav2, bras=bras, sonde=sonde)
    finally:
        arret.set()
        nav2.fermer()
        bras.fermer()
        executeur.shutdown()
        node.destroy_node()
        sonde.destroy_node()
        # contexte partagé : ne pas l'éteindre (cf. conftest.py)


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


def _publier_bras(monde, angles, secondes=2.0):
    fin = time.monotonic() + secondes
    while time.monotonic() < fin:
        message = Int32MultiArray()
        message.data = angles
        monde.pub_bras.publish(message)
        time.sleep(0.05)


def test_navigation_refusee_bras_en_extension(monde):
    _publier_bras(monde, ANGLES_EXTENSION, secondes=0.3)
    reponse = _appeler(monde, {"op": "start_skill", "skill": "navigate_to",
                               "args": {"destination": "centre"}})
    assert reponse["status"] == "PRECONDITION_FAILED"
    assert "servo 2" in reponse["reason"]
    assert monde.nav2.recus == 0, "aucun goal ne doit partir bras en extension"


def test_navigation_acceptee_bras_dans_l_enveloppe(monde):
    threading.Thread(target=_publier_bras, args=(monde, ANGLES_REPLIE, 5.0), daemon=True).start()
    assert _attendre(lambda: _etat(monde)["arm_folded"] is True, timeout=3.0), _etat(monde)

    reponse = _appeler(monde, {"op": "start_skill", "skill": "navigate_to",
                              "args": {"destination": "centre"}})
    assert reponse["status"] == "ACCEPTED", reponse
    assert _attendre(lambda: monde.nav2.recus == 1, timeout=5.0)


def test_navigation_refusee_si_les_angles_sont_perimes(monde):
    _publier_bras(monde, ANGLES_REPLIE, secondes=0.3)
    assert _attendre(lambda: _etat(monde)["arm_folded"] is True, timeout=2.0)
    # plus personne ne publie : la mesure vieillit au-delà de la limite
    assert _attendre(lambda: _etat(monde)["arm_folded"] is False, timeout=3.0), _etat(monde)

    reponse = _appeler(monde, {"op": "start_skill", "skill": "navigate_to",
                              "args": {"destination": "centre"}})
    assert reponse["status"] == "PRECONDITION_FAILED"
    assert "perimes" in reponse["reason"]


def test_le_bras_reste_commandable_hors_enveloppe(monde):
    """Sinon le directeur ne pourrait pas replier le bras qu'il refuse de déplacer."""
    _publier_bras(monde, ANGLES_EXTENSION, secondes=0.3)
    reponse = _appeler(monde, {"op": "start_skill", "skill": "arm_move",
                               "args": {"positions": [0.0] * 5, "duration_s": 0.5}})
    assert reponse["status"] == "ACCEPTED", reponse
    assert _attendre(lambda: monde.bras.recus == 1, timeout=5.0)


def test_l_etat_publie_la_mesure_du_bras(monde):
    _publier_bras(monde, ANGLES_REPLIE, secondes=0.3)
    etat = _etat(monde)
    assert etat["arm_angles"][:5] == ANGLES_REPLIE[:5]
    assert etat["arm_age_s"] is not None and etat["arm_age_s"] < 1.0
    assert etat["arm_folded"] is True
