"""Le service HTTP délègue le pilotage des capacités (REQ-OPS-030, REQ-CAPA-001).

Aucun processus n'est tué par le service : il appelle
/clawbot/capabilities/set et lit /clawbot/capabilities/state.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.req("REQ-OPS-030")

SERVICE = Path(__file__).resolve().parents[1] / "ros2_llm_bridge" / "hardware_service.py"


class FauxResultat:
    def __init__(self, success=True, state="STARTING", message="OK : démarré"):
        self.success, self.state, self.message = success, state, message


class FauxFutur:
    def __init__(self, resultat):
        self._resultat = resultat

    def done(self) -> bool:
        return True

    def result(self):
        return self._resultat


class FauxClient:
    def __init__(self, pret=True, resultat=None):
        self.pret = pret
        self.requetes = []
        self._resultat = resultat or FauxResultat()

    def wait_for_service(self, timeout_sec=None):
        return self.pret

    def call_async(self, requete):
        self.requetes.append(requete)
        return FauxFutur(self._resultat)


@pytest.fixture(scope="module")
def service():
    """Chargé par chemin : `ros2_llm_bridge` installé ne porte pas ce module."""
    nom = "hardware_service_p07"
    if nom in sys.modules:
        return sys.modules[nom]
    spec = importlib.util.spec_from_file_location(nom, SERVICE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


def test_delegue_au_gestionnaire(service):
    client = FauxClient()
    reponse = service.demander_capacite(client, "mapping", True, timeout_s=42.0)
    requete, = client.requetes
    assert requete.name == "mapping"
    assert requete.active is True
    assert requete.timeout_s == pytest.approx(42.0)
    assert reponse == {"success": True, "state": "STARTING", "message": "OK : démarré"}


def test_refus_propage(service):
    client = FauxClient(resultat=FauxResultat(False, "FAILED", "UNIT_FAILED : boom"))
    reponse = service.demander_capacite(client, "mapping", True)
    assert reponse["success"] is False and reponse["state"] == "FAILED"


def test_client_absent_refuse(service):
    with pytest.raises(Exception) as excinfo:
        service.demander_capacite(None, "mapping", True)
    assert getattr(excinfo.value, "status_code", None) == 503


def test_service_injoignable_refuse(service):
    with pytest.raises(Exception) as excinfo:
        service.demander_capacite(FauxClient(pret=False), "mapping", True)
    assert getattr(excinfo.value, "status_code", None) == 503


def test_aucun_pilotage_par_motif_dans_le_service_http():
    """La règle vaut pour le source lui-même, pas seulement pour le grep de check.sh."""
    texte = SERVICE.read_text(encoding="utf-8")
    # motifs écrits en deux morceaux : le source du test ne doit pas déclencher
    # lui-même l'étape « interdits » de scripts/check.sh
    for motif in ("p" "kill", "kill" "all", "pg" "rep", "kill" "pg"):
        assert motif not in texte, f"{motif} subsiste dans hardware_service.py"


def test_le_noeud_se_construit_avec_ses_abonnements(service):
    """Le défaut trouvé au déploiement : l'abonnement citait une méthode absente.

    Le module se chargeait très bien sans instancier le nœud ; seul le démarrage
    du service a révélé l'`AttributeError`. Ce test construit le nœud pour de vrai.
    """
    import rclpy

    if not rclpy.ok():
        rclpy.init()
    noeud = service.HardwareNode()
    try:
        assert callable(getattr(noeud, "_sur_capacites", None))
        assert isinstance(noeud.capacites, dict)
        if service.SetCapability is not None:
            assert noeud.cli_capacite is not None
    finally:
        noeud.destroy_node()


def test_les_routes_slam_passent_par_la_capacite():
    texte = SERVICE.read_text(encoding="utf-8")
    assert 'CAPACITE_SLAM = "mapping"' in texte
    assert '"/clawbot/capabilities/set"' in texte
    assert "ros2 launch" not in texte
