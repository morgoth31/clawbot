"""Nœud gestionnaire de capacités (P07).

Services `/clawbot/capabilities/set` et `/clawbot/capabilities/list`, état publié
sur `/clawbot/capabilities/state` (RELIABLE + TRANSIENT_LOCAL, REQ-CAPA-006).
Aucun mouvement : ce nœud ne publie que sur ses propres topics.
"""
from __future__ import annotations

import json
import sys

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from clawbot_interfaces.srv import ListCapabilities, SetCapability

from .backend import ErreurBackend, FauxBackend, SystemdBackend
from .controleur import Controleur, Etat
from .etat import PublieurEtat
from .manifeste import charger
from .sondes import fabriquer

QOS_ETAT = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.TRANSIENT_LOCAL)

MANIFESTE_PAR_DEFAUT = "/home/jetson/clawbot/install/clawbot_capabilities/share/clawbot_capabilities/config/capabilities.yaml"


class GestionnaireCapacites(Node):
    def __init__(self):
        super().__init__("capability_manager")
        self.declare_parameter("manifest_path", MANIFESTE_PAR_DEFAUT)
        self.declare_parameter("backend", "systemd")
        self.declare_parameter("autostart_always_on", True)
        self.declare_parameter("periode_etat_s", 0.2)
        # 0,2 Hz : la reconciliation lit systemd, elle n'a pas besoin d'aller plus vite.
        self.declare_parameter("periode_reconciliation_s", 5.0)

        chemin = self.get_parameter("manifest_path").value
        manifeste = charger(chemin)
        mode = self.get_parameter("backend").value
        self.backend = SystemdBackend() if mode == "systemd" else FauxBackend()
        self.controleur = Controleur(manifeste, self.backend,
                                     fabrique_sondes=lambda c: fabriquer(self, c))
        self.publieur = PublieurEtat(self.create_publisher(
            String, "/clawbot/capabilities/state", QOS_ETAT))

        self.create_service(SetCapability, "/clawbot/capabilities/set", self._sur_set)
        self.create_service(ListCapabilities, "/clawbot/capabilities/list", self._sur_list)
        self.create_timer(float(self.get_parameter("periode_etat_s").value), self._sur_timer)
        self.create_timer(float(self.get_parameter("periode_reconciliation_s").value),
                          self._sur_reconciliation)

        self.get_logger().info(
            f"gestionnaire pret : {len(manifeste)} capacites, backend {mode}, "
            f"manifeste {chemin}")
        if bool(self.get_parameter("autostart_always_on").value):
            for nom, capacite in manifeste.items():
                if capacite.always_on and capacite.units:
                    resultat = self.controleur.demander(nom, actif=True)
                    self.get_logger().info(f"demarrage {nom} : {resultat.code.value} "
                                           f"({resultat.message})")
        self.publier_etat()

    # ── services ─────────────────────────────────────────────────────────────
    def _sur_set(self, requete, reponse):
        try:
            resultat = self.controleur.demander(requete.name, actif=requete.active,
                                               timeout_s=requete.timeout_s or None)
        except ErreurBackend as exc:            # pragma: no cover - défense en profondeur
            reponse.success, reponse.state = False, Etat.FAILED.value
            reponse.message = str(exc)
            return reponse
        reponse.success = resultat.success
        reponse.state = resultat.etat.value
        reponse.message = f"{resultat.code.value} : {resultat.message}"
        self.get_logger().info(
            f"set {requete.name} active={requete.active} -> {reponse.state} "
            f"({resultat.code.value})")
        self.publier_etat()
        return reponse

    def _sur_list(self, requete, reponse):
        reponse.capabilities_json = json.dumps(
            list(self.controleur.instantane().values()), ensure_ascii=False)
        return reponse

    # ── état ─────────────────────────────────────────────────────────────────
    def publier_etat(self) -> None:
        if self.publieur.publier(self.controleur.instantane()):
            for nom, champs in self.controleur.instantane().items():
                if champs["state"] not in ("INACTIVE",):
                    self.get_logger().debug(f"{nom} = {champs['state']}")

    def _sur_reconciliation(self):
        """Recalcule l'etat depuis systemd (REQ-CAPA-010) et signale les ecarts."""
        try:
            changements = self.controleur.reconcilier()
        except Exception as exc:  # noqa: BLE001 — la reconciliation ne doit pas tuer le noeud
            self.get_logger().error(f"reconciliation impossible : {exc}")
            return
        for nom in changements:
            self.get_logger().warning(
                f"etat de {nom} constate sans demande : "
                f"{self.controleur.etiquette(nom).value}")
        if changements:
            self.publier_etat()

    def _sur_timer(self):
        self.controleur.rafraichir()
        self.publier_etat()


def main(argv=None) -> int:
    rclpy.init(args=argv)
    noeud = None
    try:
        noeud = GestionnaireCapacites()
        rclpy.spin(noeud)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if noeud is not None:
            noeud.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
