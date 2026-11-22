"""L'arrêt du service directeur termine la tâche en cours (dette « ExecStop »).

Le défaut visé : un `systemctl restart clawbot-director` laissait la tâche `RUNNING` et le goal
actif côté serveur d'action, sans personne pour l'attendre. Le test ne se contente pas de lire le
fichier d'unité : il **exécute le script** que l'unité appelle, contre un directeur réel en domaine
99, avec un faux serveur d'action qui ne rend jamais la main.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RACINE = Path(__file__).resolve().parents[2]
UNIT = RACINE / "services" / "clawbot-director.service"
SCRIPT = RACINE / "scripts" / "annuler_tache_service.sh"
ETAPE = {"skill": "arm_move",
         "args": {"positions": [0.0] * 5, "duration_s": 0.5, "timeout_s": 60.0}}


# ── le contrat écrit dans l'unité ────────────────────────────────────────────
def test_l_unite_annule_la_tache_a_l_arret():
    contenu = UNIT.read_text(encoding="utf-8")
    assert "ExecStop=" in contenu, "un arret doit annuler la tache en cours"
    assert "annuler_tache_service.sh" in contenu
    assert "TimeoutStopSec=" in contenu, "sans delai, un ExecStop muet bloque l'arret"


def test_le_script_est_executable_et_annule_sans_se_deguiser_en_securite():
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK), "l'unite appelle le script directement"
    contenu = SCRIPT.read_text(encoding="utf-8")
    assert 'cancel_task' in contenu
    # un motif de la famille « safety » ferait passer une annulation d'exploitation pour un arrêt
    # de sécurité dans l'historique du directeur
    assert 'arret_service' in contenu
    assert "safety" not in contenu.split("cancel_task", 1)[1].split("}", 1)[0]
    assert contenu.rstrip().endswith("exit 0"), "l'echec du script ne doit pas bloquer l'arret"


# ── le comportement, en domaine 99 ──────────────────────────────────────────
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


@pytest.fixture()
def monde():
    node = DirectorNode()        # contexte rclpy fourni par conftest.py
    executeur = SingleThreadedExecutor()
    executeur.add_node(node)
    sonde = Node("sonde_arret_service")
    pub_safety = sonde.create_publisher(String, "/safety/state", 10)
    pub_bras = sonde.create_publisher(Int32MultiArray, "/arm/servo_angles", 10)
    executeur.add_node(sonde)
    threading.Thread(target=executeur.spin, daemon=True).start()

    bras = FauxBras(mode="silencieux")
    arret = threading.Event()

    def _alimenter():
        angles = Int32MultiArray()
        angles.data = [90, 180, 0, 0, 90, 149]
        while not arret.is_set():
            pub_safety.publish(String(data="OK"))
            pub_bras.publish(angles)
            time.sleep(0.05)

    try:
        assert _attendre(lambda: pub_safety.get_subscription_count() > 0, timeout=5.0)
        while node.etat()["safety"] != "OK" or node.etat()["safety_stale"]:
            pub_safety.publish(String(data="OK"))
            time.sleep(0.05)
        threading.Thread(target=_alimenter, daemon=True).start()
        time.sleep(0.5)
        yield SimpleNamespace(node=node, bras=bras, sonde=sonde)
    finally:
        arret.set()
        bras.fermer()
        executeur.shutdown()
        node.destroy_node()
        sonde.destroy_node()
        # contexte partagé : ne pas l'éteindre (cf. conftest.py)


def _attendre(predicate, timeout=3.0, period=0.01):
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


def test_le_script_d_execstop_termine_la_tache_en_cours(monde):
    """Le goal ne rend jamais la main : seul l'ExecStop peut terminer la tâche."""
    demarree = _appeler(monde, {"op": "start_sequence", "steps": [ETAPE]})
    assert demarree["status"] == "ACCEPTED", demarree
    assert _attendre(lambda: monde.bras.recus == 1, timeout=5.0), "le goal doit etre en vol"

    environnement = dict(os.environ)
    environnement["ROS_DOMAIN_ID"] = "99"
    resultat = subprocess.run(["/bin/bash", str(SCRIPT)], capture_output=True, text=True,
                              env=environnement, timeout=30)

    assert resultat.returncode == 0, resultat.stderr
    assert "CANCELLED" in (resultat.stderr + resultat.stdout), resultat.stderr
    etat = _appeler(monde, {"op": "get_task"})["task"]
    assert etat["state"] == "CANCELLED", etat
    assert etat["reason"] == "arret_service", etat
    assert _attendre(lambda: monde.bras.annules >= 1, timeout=3.0), "goal non annule"
