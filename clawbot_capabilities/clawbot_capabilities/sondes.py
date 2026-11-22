"""Sondes de disponibilité (REQ-CAPA-002).

Une sonde répond à une seule question : « la capacité sert-elle réellement ? ».
Elle est créée à l'activation et détruite à l'arrêt — l'abonnement ne dure donc que
la fenêtre de démarrage, ce qui évite le coût permanent mesuré en P05 sur les flux
image. La surveillance continue reste le travail de `clawbot_health`.
"""
from __future__ import annotations

import time
from collections import deque

QOS_SONDE = 5          # profondeur volontairement faible : on ne garde que des horodatages


class SondeTopic:
    """Vraie si des messages arrivent à la cadence demandée (ou assez récemment)."""

    def __init__(self, node, topic: str, min_hz: float | None = None,
                 max_age_s: float | None = None, fenetre_s: float = 5.0):
        self.node = node
        self.topic = topic
        self.min_hz = min_hz
        self.max_age_s = max_age_s
        self.fenetre_s = fenetre_s
        self.horodatages: deque[float] = deque(maxlen=200)
        self._abonnement = None
        self._type: str | None = None
        self._echec: str | None = None

    def _type_du_topic(self) -> str | None:
        for nom, types in self.node.get_topic_names_and_types():
            if nom == self.topic and types:
                return types[0]
        return None

    def _ouvrir(self) -> bool:
        if self._abonnement is not None:
            return True
        if self._echec is not None:
            return False
        self._type = self._type_du_topic()
        if self._type is None:
            self._echec = f"aucun éditeur sur {self.topic}"
            return False
        from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
        from rosidl_runtime_py.utilities import get_message

        qos = QoSProfile(depth=QOS_SONDE, history=HistoryPolicy.KEEP_LAST,
                         reliability=ReliabilityPolicy.BEST_EFFORT)
        try:
            classe = get_message(self._type)
        except (AttributeError, ModuleNotFoundError, ValueError) as exc:
            self._echec = f"type {self._type} non résoluble ({exc})"
            return False
        # rclpy n'a pas de `create_generic_subscription` (c'est une API rclcpp) :
        # la sonde s'abonne typé. Elle vit le temps de l'activation seulement, donc
        # la copie des messages reste bornée à cette fenêtre (cf. P05).
        # L'abonnement est conservé : sans référence, il est collecté et ne reçoit rien.
        self._abonnement = self.node.create_subscription(
            classe, self.topic, self._sur_message, qos)
        return True

    def _sur_message(self, _charge) -> None:
        self.horodatages.append(time.monotonic())

    def preter(self) -> bool:
        if not self._ouvrir():
            return False
        maintenant = time.monotonic()
        recents = [t for t in self.horodatages if maintenant - t <= self.fenetre_s]
        if self.max_age_s is not None:
            return bool(recents) and (maintenant - recents[-1]) <= self.max_age_s
        if not recents or len(recents) < 3:
            return False
        intervalle = recents[-1] - recents[0]
        if intervalle < 1.0:
            return False                     # fenêtre trop courte pour conclure
        return (len(recents) - 1) / intervalle >= self.min_hz

    def fermer(self) -> None:
        if self._abonnement is not None:
            self.node.destroy_subscription(self._abonnement)
            self._abonnement = None


class SondeAction:
    """Vraie si un serveur d'action du nom donné est joignable."""

    def __init__(self, node, action: str):
        self.node = node
        self.action = action.rstrip("/")

    def preter(self) -> bool:
        vise = f"{self.action}/_action/send_goal"
        return any(nom == vise for nom, _ in self.node.get_service_names_and_types())

    def fermer(self) -> None:
        return None


def fabriquer(node, capacite) -> list:
    """Construit les sondes d'une capacité à partir de son `ready_when`."""
    sondes = []
    for condition in capacite.ready_when:
        if "action" in condition:
            sondes.append(SondeAction(node, condition["action"]))
        else:
            sondes.append(SondeTopic(node, condition["topic"],
                                     min_hz=condition.get("min_hz"),
                                     max_age_s=condition.get("max_age_s")))
    return sondes
