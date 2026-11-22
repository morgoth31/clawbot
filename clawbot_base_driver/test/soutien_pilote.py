"""Faux matériel, fausse horloge et faux journal pour les tests du pilote (P03).

Le pilote reçoit une fabrique `rosmaster_factory` : aucun test n'ouvre de port
série, et l'horloge du nœud est remplaçable pour rendre les délais déterministes.
"""
from __future__ import annotations

import rclpy


class FauxRosmaster:
    """Reproduit la surface de Rosmaster utilisée par le pilote."""

    def __init__(self, **_kwargs):
        self.appels = []          # (vx, vy, wz) reçus par set_car_motion
        self.car_type_envoye = None
        self.torque = None
        self.erreurs = []

    # ── écriture ─────────────────────────────────────────────────────────────
    def set_car_motion(self, vx, vy, wz):
        self.appels.append((vx, vy, wz))

    def set_car_type(self, car_type):
        self.car_type_envoye = car_type

    def set_auto_report_state(self, *_a, **_k):
        pass

    def create_receive_threading(self):
        pass

    def set_uart_servo_torque(self, etat):
        self.torque = etat

    def set_colorful_effect(self, *_a, **_k):
        pass

    def set_beep(self, *_a):
        pass

    def set_uart_servo_angle(self, *_a):
        pass

    def set_pwm_servo(self, *_a):
        pass

    # ── lecture ──────────────────────────────────────────────────────────────
    def get_car_type_from_machine(self):
        return 2

    def get_version(self):
        return 1.0

    def get_motion_pid(self):
        return (0.0, 0.0, 0.0)

    def get_battery_voltage(self):
        return 11.9

    def get_accelerometer_data(self):
        return (0.0, 0.0, 9.81)

    def get_gyroscope_data(self):
        return (0.0, 0.0, 0.0)

    def get_magnetometer_data(self):
        return (0.0, 0.0, 0.0)

    def get_motion_data(self):
        return (0.0, 0.0, 0.0)

    def get_uart_servo_angle(self, _servo_id):
        return 90


class FausseHorloge:
    """Horloge monotone contrôlée par le test."""

    def __init__(self, depart=1000.0):
        self.t = depart

    def now_s(self):
        return self.t

    def avance(self, dt):
        self.t += dt


class FauxJournal:
    """Capture les messages du nœud au lieu de les écrire dans le journal."""

    def __init__(self):
        self.infos = []
        self.avertissements = []
        self.erreurs = []

    def info(self, message, *_a, **_k):
        self.infos.append(str(message))

    def warn(self, message, *_a, **_k):
        self.avertissements.append(str(message))

    def error(self, message, *_a, **_k):
        self.erreurs.append(str(message))


def demarrer_rclpy():
    """Initialise rclpy une seule fois pour tout le processus de test."""
    if not rclpy.ok():
        rclpy.init()


def arreter(node):
    """Detruit le noeud ET ferme le contexte : sinon le test suivant ne peut plus
    appeler rclpy.init() (« Context.init() must only be called once »)."""
    node.destroy_node()
    rclpy.try_shutdown()


def instancier(module, faux, horloge, journal, **parametres):
    """Construit le pilote avec le faux matériel et les remplacements de test."""
    demarrer_rclpy()
    node = module.yahboomcar_driver(
        "driver_node", rosmaster_factory=lambda **_k: faux, **parametres
    )
    node.now_s = horloge.now_s
    node.get_logger = lambda: journal
    return node
