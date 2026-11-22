"""Publication de l'état des capacités (REQ-CAPA-006)."""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.req("REQ-CAPA-006")


class FauxPublisher:
    def __init__(self):
        self.messages: list[str] = []

    def publish(self, message):
        self.messages.append(message.data)


def test_qos_transient_local():
    from rclpy.qos import DurabilityPolicy, ReliabilityPolicy

    from clawbot_capabilities.gestionnaire import QOS_ETAT

    assert QOS_ETAT.durability == DurabilityPolicy.TRANSIENT_LOCAL
    assert QOS_ETAT.reliability == ReliabilityPolicy.RELIABLE
    assert QOS_ETAT.depth >= 1


def test_publie_quand_l_etat_change():
    from clawbot_capabilities.etat import PublieurEtat

    publisher = FauxPublisher()
    publieur = PublieurEtat(publisher)
    instantane = {"navigation": {"state": "STARTING"}}
    assert publieur.publier(instantane) is True
    assert publieur.publier({"navigation": {"state": "STARTING"}}) is False
    assert publieur.publier({"navigation": {"state": "ACTIVE"}}) is True
    assert len(publisher.messages) == 2


def test_json_contient_les_champs_du_contrat():
    from clawbot_capabilities.etat import PublieurEtat

    publisher = FauxPublisher()
    PublieurEtat(publisher).publier({
        "mapping": {"name": "mapping", "state": "ACTIVE", "units": ["clawbot-slam.service"],
                    "requires": ["base", "lidar"], "conflicts": ["navigation"], "stale_flows": []},
    })
    charge = json.loads(publisher.messages[0])
    assert charge["capabilities"][0] == {
        "name": "mapping", "state": "ACTIVE", "units": ["clawbot-slam.service"],
        "requires": ["base", "lidar"], "conflicts": ["navigation"], "stale_flows": [],
    }


def test_champ_inconnu_refuse():
    from clawbot_capabilities.etat import PublieurEtat

    with pytest.raises(ValueError, match="champ inconnu"):
        PublieurEtat(FauxPublisher()).publier({"base": {"state": "ACTIVE", "humeur": "bonne"}})
