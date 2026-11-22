"""Moniteur de santé des flux : /clawbot/health à 1 Hz et /diagnostics.

Il observe, il ne décide pas : aucun éditeur de vitesse, aucun e-stop. La réaction
à un flux périmé reste à l'arbitre (pour /scan) et à l'exécutif (P09).

Chaque flux est abonné en **brut** (`raw=True`, BEST_EFFORT, profondeur 1) : le
callback ne fait qu'enregistrer un instant de réception, aucun message image ou
nuage de points n'est désérialisé (REQ-HEALTH-004).
"""
from __future__ import annotations

import json
import sys
from time import perf_counter

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Float32, String

from clawbot_interfaces.msg import RobotHealth

from . import manifeste
from .estimateur import (LEVEL_ERROR, LEVEL_OK, LEVEL_WARN, EstimateurFlux, EtatFlux,
                         niveau_global, surveilles)

CAPACITES_PAR_DEFAUT = ["base", "lidar", "wrist_vision", "depth_vision"]

# Flux dont la valeur est publiée dans RobotHealth : ils reçoivent UN abonnement typé
# (ils alimentent aussi l'estimateur). Abonner deux fois le même topic avec deux types
# différents est refusé par DDS — constaté au premier démarrage du binaire sur /voltage.
FLUX_TYPES = {"/voltage"}


def _lecture_seule():
    return ParameterDescriptor(read_only=True)


class HealthMonitor(Node):
    def __init__(self, context=None, parameter_overrides=None):
        super().__init__("health_monitor", context=context,
                         parameter_overrides=parameter_overrides)
        d = _lecture_seule()
        self.declare_parameter("flows_file", manifeste.chemin_par_defaut(), d)
        self.declare_parameter("assume_active_capabilities", CAPACITES_PAR_DEFAUT, d)
        self.declare_parameter("publish_rate_hz", 1.0, d)
        self.declare_parameter("rate_window_s", 5.0, d)

        self._fenetre = float(self.get_parameter("rate_window_s").value)
        self._flux = manifeste.charger(self.get_parameter("flows_file").value)
        self._capacites = list(self.get_parameter("assume_active_capabilities").value)
        self._capacites_reelles = False      # vrai dès que /clawbot/capabilities/state parle
        self._estimateurs = {f.topic: EstimateurFlux(self._fenetre) for f in self._flux}

        self.safety_state = "UNKNOWN"
        self.estop_latched = False
        self.voltage = float("nan")
        self.last_tick_ms = 0.0

        qos_brut = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                              durability=DurabilityPolicy.VOLATILE)
        for flux in self._flux:
            if flux.topic in FLUX_TYPES:
                continue        # abonnement typé plus bas, il alimente aussi l'estimateur
            self.create_subscription(String, flux.topic,
                                     lambda _msg, topic=flux.topic: self._on_flux(topic),
                                     qos_brut, raw=True)

        self.create_subscription(String, "/safety/state", self._on_safety, 10)
        self.create_subscription(Float32, "/voltage", self._on_voltage, 10)
        self.create_subscription(String, "/clawbot/capabilities/state",
                                 self._on_capacites, 10)

        self.pub_health = self.create_publisher(RobotHealth, "/clawbot/health", 10)
        self.pub_diag = self.create_publisher(DiagnosticArray, "/diagnostics", 10)
        self.create_timer(1.0 / float(self.get_parameter("publish_rate_hz").value), self.tick)

    def _now(self):
        return self.get_clock().now().nanoseconds / 1e9

    # ── entrées ──────────────────────────────────────────────────────────────

    def _on_flux(self, topic):
        self._estimateurs[topic].enregistrer(self._now())

    def _on_safety(self, msg):
        brut = msg.data.strip()
        try:
            charge = json.loads(brut)
        except ValueError:
            self.safety_state = brut.upper()
            return
        self.safety_state = str(charge.get("state", "UNKNOWN"))
        self.estop_latched = bool(charge.get("estop_latched", False))

    def _on_voltage(self, msg):
        self.voltage = float(msg.data)
        est = self._estimateurs.get("/voltage")
        if est is not None:
            est.enregistrer(self._now())

    def _on_capacites(self, msg):
        """P07 publiera la liste réelle ; tant qu'elle se tait, le paramètre fait foi."""
        try:
            charge = json.loads(msg.data)
        except ValueError:
            return
        actives = charge.get("active") if isinstance(charge, dict) else charge
        if isinstance(actives, list):
            self._capacites = [str(c) for c in actives]
            self._capacites_reelles = True

    # ── boucle ───────────────────────────────────────────────────────────────

    def etats(self, maintenant=None):
        """États des flux dont la capacité est active (REQ-HEALTH-006)."""
        maintenant = self._now() if maintenant is None else maintenant
        resultat = []
        for flux in surveilles(self._flux, self._capacites):
            est = self._estimateurs[flux.topic]
            age = est.age(maintenant)
            cadence = est.cadence(maintenant)
            perime = age > flux.max_age_s
            basse = (not perime) and est.nombre() >= 2 and cadence < flux.min_hz
            resultat.append(EtatFlux(flux=flux, age=age, cadence=cadence,
                                     perime=perime, cadence_basse=basse))
        return resultat

    def tick(self):
        debut = perf_counter()
        maintenant = self._now()
        etats = self.etats(maintenant)
        niveau = niveau_global(etats)

        msg = RobotHealth()
        msg.stamp = self.get_clock().now().to_msg()
        msg.level = niveau
        msg.active_capabilities = list(self._capacites)
        msg.stale_flows = [e.flux.topic for e in etats if e.perime]
        msg.safety_state = self.safety_state
        msg.estop_latched = self.estop_latched
        msg.voltage = float(self.voltage) if self.voltage == self.voltage else 0.0
        msg.detail_json = json.dumps({
            "flows": [{"topic": e.flux.topic,
                       "hz": None if e.cadence is None else round(e.cadence, 3),
                       "age_s": None if e.age == float("inf") else round(e.age, 3),
                       "critical": e.flux.critical,
                       "state": "STALE" if e.perime else ("SLOW" if e.cadence_basse else "OK")}
                      for e in etats],
            "capabilities_from_topic": self._capacites_reelles,
        }, sort_keys=True)
        self.pub_health.publish(msg)

        diag = DiagnosticArray()
        diag.header.stamp = msg.stamp
        for e in etats:
            statut = DiagnosticStatus()
            statut.name = f"clawbot_health: {e.flux.topic}"
            statut.hardware_id = e.flux.capability
            if e.perime:
                statut.level = DiagnosticStatus.ERROR if e.flux.critical else DiagnosticStatus.WARN
                statut.message = "flux perime"
            elif e.cadence_basse:
                statut.level = DiagnosticStatus.WARN
                statut.message = "cadence sous le seuil"
            else:
                statut.level = DiagnosticStatus.OK
                statut.message = "flux frais"
            statut.values = [
                KeyValue(key="hz", value=f"{e.cadence:.2f}"),
                KeyValue(key="min_hz", value=f"{e.flux.min_hz:.2f}"),
                KeyValue(key="age_s", value="inf" if e.age == float("inf") else f"{e.age:.2f}"),
                KeyValue(key="max_age_s", value=f"{e.flux.max_age_s:.2f}"),
                KeyValue(key="critical", value=str(e.flux.critical).lower()),
            ]
            diag.status.append(statut)
        self.pub_diag.publish(diag)

        self.last_tick_ms = (perf_counter() - debut) * 1000.0
        if niveau != LEVEL_OK:
            self.get_logger().debug(f"niveau={niveau} perimes={msg.stale_flows}")


def main():
    rclpy.init(args=sys.argv[1:])
    node = HealthMonitor()
    node.get_logger().info(
        f"moniteur pret : {len(node._flux)} flux declares, "
        f"capacites actives {node._capacites}")
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    return 0
