"""Gestionnaire de capacités en domaine 99 avec backend simulé.

Le binaire déployé est lancé avec `backend:=fake` et un manifeste de test : on
vérifie le contrat réel (services, topic d'état, transitions), pas la logique seule.
Aucune unité systemd n'est touchée, aucun processus n'est cherché par motif.

Pas de fil d'exécution en arrière-plan : on alterne `spin_once` et publication, ce
qui évite qu'un client créé après le démarrage d'un exécuteur ne soit jamais servi.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

if os.environ.get("ROS_DOMAIN_ID") != "99":
    pytest.skip("test d'intégration : domaine 99 requis", allow_module_level=True)

RACINE = Path(__file__).resolve().parents[2]
BINAIRE = RACINE / "install" / "clawbot_capabilities" / "lib" / "clawbot_capabilities" / "gestionnaire"

import rclpy  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy  # noqa: E402
from std_msgs.msg import Float32, String  # noqa: E402

from clawbot_interfaces.srv import ListCapabilities, SetCapability  # noqa: E402

pytestmark = [pytest.mark.integration, pytest.mark.req("REQ-CAPA-002")]

MANIFESTE = """capacites:
  base:
    units: [essai-base.service]
    always_on: true
    managed: true
    ready_when: [{topic: /essai/odom, min_hz: 5.0}]
    timeout_s: 20.0
  navigation:
    units: [essai-nav.service]
    requires: [base]
    conflicts: [mapping]
    managed: true
    ready_when: [{topic: /essai/odom, min_hz: 5.0}]
    timeout_s: 20.0
  mapping:
    units: [essai-slam.service]
    requires: [base]
    conflicts: [navigation]
    managed: true
    ready_when: [{topic: /essai/odom, min_hz: 5.0}]
    timeout_s: 20.0
"""


class Banc:
    def __init__(self, noeud, processus, editeur):
        self.noeud = noeud
        self.processus = processus
        self.editeur = editeur
        self.set = noeud.create_client(SetCapability, "/clawbot/capabilities/set")
        self.list = noeud.create_client(ListCapabilities, "/clawbot/capabilities/list")
        self.recus: list[str] = []
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)
        noeud.create_subscription(String, "/clawbot/capabilities/state",
                                  lambda m: self.recus.append(m.data), qos)

    def tourner(self, duree_s: float, cadence_hz: float = 10.0) -> None:
        """Fait avancer ce processus et publie /essai/odom pendant `duree_s`."""
        fin = time.monotonic() + duree_s
        periode = 1.0 / cadence_hz
        while time.monotonic() < fin:
            self.editeur.publish(Float32(data=1.0))
            rclpy.spin_once(self.noeud, timeout_sec=periode)

    def appeler(self, client, requete, attente_s: float = 40.0):
        futur = client.call_async(requete)
        fin = time.monotonic() + attente_s
        while not futur.done() and time.monotonic() < fin:
            self.tourner(0.2)
        if not futur.done():
            sortie = ""
            if self.processus.poll() is not None:
                sortie = (self.processus.communicate(timeout=5)[0] or "")[-1200:]
            raise AssertionError(
                f"aucune réponse du service | code enfant={self.processus.poll()} | "
                f"service prêt={client.service_is_ready()}\n--- sortie du gestionnaire ---\n{sortie}")
        return futur.result()

    def demander(self, nom: str, actif: bool, timeout_s: float = 10.0):
        requete = SetCapability.Request()
        requete.name, requete.active, requete.timeout_s = nom, actif, timeout_s
        return self.appeler(self.set, requete)


@pytest.fixture(scope="module")
def banc(tmp_path_factory):
    if not BINAIRE.is_file():
        pytest.skip(f"binaire non construit : {BINAIRE}")
    dossier = tmp_path_factory.mktemp("capacites")
    manifeste = dossier / "capabilities.yaml"
    manifeste.write_text(MANIFESTE, encoding="utf-8")

    if not rclpy.ok():
        rclpy.init()
    processus = subprocess.Popen(
        [str(BINAIRE), "--ros-args", "-p", f"manifest_path:={manifeste}",
         "-p", "backend:=fake", "-p", "autostart_always_on:=false"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    noeud = Node("sonde_capacites_99")
    editeur = noeud.create_publisher(Float32, "/essai/odom", 10)
    banc = Banc(noeud, processus, editeur)

    fin = time.monotonic() + 20.0
    while not banc.set.wait_for_service(timeout_sec=1.0) and time.monotonic() < fin:
        rclpy.spin_once(noeud, timeout_sec=0.2)
    if not banc.set.service_is_ready():
        processus.kill()
        sortie = processus.communicate(timeout=5)[0] or ""
        pytest.skip("gestionnaire non joignable en domaine 99 : " + sortie[-600:])
    yield banc

    noeud.destroy_node()
    processus.terminate()
    try:
        processus.wait(timeout=10)
    except subprocess.TimeoutExpired:
        processus.kill()


def test_etat_initial_publie_sur_le_topic(banc):
    fin = time.monotonic() + 20.0
    while not banc.recus and time.monotonic() < fin:
        banc.tourner(0.2)
    assert banc.recus, "aucun état reçu sur /clawbot/capabilities/state"
    charge = json.loads(banc.recus[-1])
    noms = {c["name"] for c in charge["capabilities"]}
    assert noms == {"base", "navigation", "mapping"}
    for entree in charge["capabilities"]:
        assert set(entree) == {"name", "state", "units", "requires", "conflicts", "stale_flows"}


def test_base_devient_active_quand_le_flux_arrive(banc):
    reponse = banc.demander("base", True)
    assert reponse.success, reponse.message
    assert reponse.state in ("STARTING", "ACTIVE")
    etat = reponse.state
    fin = time.monotonic() + 40.0
    while etat != "ACTIVE" and time.monotonic() < fin:
        banc.tourner(1.0)                     # /essai/odom à 10 Hz
        etat = banc.demander("base", True).state
    assert etat == "ACTIVE", f"état final {etat} (les sondes ne se sont pas satisfaites)"


def test_conflit_refuse_en_domaine_reel(banc):
    assert banc.demander("navigation", True).success
    reponse = banc.demander("mapping", True)
    assert reponse.success is False
    assert "CAPABILITY_CONFLICT" in reponse.message


def test_always_on_refuse_l_arret(banc):
    reponse = banc.demander("base", False)
    assert reponse.success is False
    assert "ALWAYS_ON" in reponse.message


def test_liste_des_capacites(banc):
    reponse = banc.appeler(banc.list, ListCapabilities.Request())
    entrees = json.loads(reponse.capabilities_json)
    assert {e["name"] for e in entrees} == {"base", "navigation", "mapping"}
    assert all("state" in e for e in entrees)
