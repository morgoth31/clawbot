"""Arbitre réflexe du Système 1 : propriétaire unique de la sortie actionneurs.

20 Hz, aucune allocation en boucle, aucune planification. Il reçoit des entrées
nommées (`/cmd_vel/teleop`, `/cmd_vel/nav`, `/cmd_vel/skill` ; l'ancienne entrée
`legacy` /cmd_vel a été retirée en P14), retient la plus prioritaire non expirée,
applique les garde-fous de `decide()` et publie la consigne réellement exécutable sur
`/cmd_vel_safe`. Le driver n'écoute plus que ce topic : un seul écrivain par actionneur.

Un arrêt d'urgence (`/safety/estop`) annule la sortie et reste verrouillé ; il ne
se lève que par `/safety/reset_estop`, et seulement si le signal est retombé.
"""
import json
import math
import sys
import time
from time import perf_counter

import rclpy
from geometry_msgs.msg import Twist
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Imu, LaserScan
from std_msgs.msg import Bool, Float32, Int32MultiArray, String
from std_srvs.srv import Trigger

from .thresholds import STALE_S, battery_state, is_stale, obstacle_stop, tilt_state

CMD_TIMEOUT_S = 0.5   # au-delà, la dernière commande est périmée et remise à zéro

# Table §4 du référentiel : (nom, topic, priorité, expiration).
ENTREES_PAR_DEFAUT = (
    ("teleop", "/cmd_vel/teleop", 100, 0.5),
    ("nav", "/cmd_vel/nav", 50, 0.5),
    ("skill", "/cmd_vel/skill", 40, 0.5),
)

FENETRE_MESURE_S = 10.0
GARDE_CALLBACK_MS = 20.0


def _rpy(q):
    sinr = 2.0000000 * (q.w * q.x + q.y * q.z)
    cosr = 1.0 - 2.0 * (q.x * q.x + q.y * q.y)
    roll = math.degrees(math.atan2(sinr, cosr))
    sinp = max(-1.0, min(1.0, 2.0 * (q.w * q.y - q.z * q.x)))
    return roll, math.degrees(math.asin(sinp))


def decide(cmd, front_m, roll, pitch, servo2, samples, age_scan, age_imu):
    """Décision pure : l'état de sécurité et la consigne à publier."""
    moving = any(abs(v) > 1e-6 for v in (cmd[0], cmd[1], cmd[2]))
    if is_stale(age_scan) or is_stale(age_imu):
        return "SENSOR_STALE", (0.0, 0.0, 0.0)
    if obstacle_stop(front_m, moving):
        return "STOP", (0.0, 0.0, 0.0)
    etat = tilt_state(roll, pitch, servo2)
    if etat != "ok":
        # HOLD, DROP_TORQUE ou FREEZE : l'aval doit pouvoir distinguer « maintenir » de
        # « couper le couple », ce ne sont pas les mêmes gestes sur le bras.
        return etat.upper(), (0.0, 0.0, 0.0)
    if battery_state(samples, time.time()) == "low":
        return "BATTERY_LOW", (0.0, 0.0, 0.0)
    return "OK", cmd


def _lecture_seule():
    return ParameterDescriptor(read_only=True)


class Arbitrator(Node):
    def __init__(self, context=None):
        super().__init__("safety_arbitrator", context=context)
        self._declarer_parametres()

        self.cmd = (0.0, 0.0, 0.0)
        self.front = float("nan")
        self.roll = 0.0
        self.pitch = 0.0
        self.servo2 = 96.0
        self.samples = []
        self.age_scan = 99.0
        self.age_imu = 99.0
        self.derniere_sortie = (0.0, 0.0, 0.0)
        self.etat = {"state": "OK", "source": None, "estop_latched": False,
                     "max_callback_ms": 0.0}
        self._durees = []          # (instant, ms) sur la fenêtre glissante

        self._estop_latche = False
        self._estop_dernier = False

        self.pub_safe = self.create_publisher(Twist, "/cmd_vel_safe", 10)
        self.pub_hold = self.create_publisher(Bool, "/safety/hold", 10)
        self.pub_state = self.create_publisher(String, "/safety/state", 10)

        for nom, entree in self._entrees.items():
            qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
            self.create_subscription(Twist, entree["topic"],
                                     lambda msg, n=nom: self._on_input(n, msg), qos)

        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)
        self.create_subscription(Float32, "/voltage", self.on_volt, 10)
        self.create_subscription(Imu, "/imu/data_raw", self.on_imu, 20)
        self.create_subscription(Int32MultiArray, "/arm/servo_angles", self.on_arm, 10)

        qos_estop = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                               durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(Bool, "/safety/estop", self._on_estop, qos_estop)
        self.create_service(Trigger, "/safety/reset_estop", self._sur_reset_estop)

        self.last_scan = self.last_imu = 0.0
        self.create_timer(1.0 / float(self.get_parameter("publish_rate_hz").value), self.tick)

    # ── configuration ────────────────────────────────────────────────────────

    def _declarer_parametres(self):
        d = _lecture_seule()
        self.declare_parameter("publish_rate_hz", 20.0, d)
        self.declare_parameter("stale_s", STALE_S, d)
        self.declare_parameter("cmd_timeout_s", CMD_TIMEOUT_S, d)
        self.declare_parameter("inputs.names", [n for n, *_ in ENTREES_PAR_DEFAUT], d)
        for nom, topic, priorite, timeout in ENTREES_PAR_DEFAUT:
            self.declare_parameter(f"inputs.{nom}.topic", topic, d)
            self.declare_parameter(f"inputs.{nom}.priority", priorite, d)
            self.declare_parameter(f"inputs.{nom}.timeout_s", timeout, d)
        # le YAML peut décrire d'autres entrées que les quatre par défaut
        for nom in self.get_parameter("inputs.names").value:
            if nom in [n for n, *_ in ENTREES_PAR_DEFAUT]:
                continue
            self.declare_parameter(f"inputs.{nom}.topic", f"/cmd_vel/{nom}", d)
            self.declare_parameter(f"inputs.{nom}.priority", 1, d)
            self.declare_parameter(f"inputs.{nom}.timeout_s", CMD_TIMEOUT_S, d)

        self._entrees = {}
        for nom in self.get_parameter("inputs.names").value:
            self._entrees[nom] = {
                "topic": self.get_parameter(f"inputs.{nom}.topic").value,
                "priority": int(self.get_parameter(f"inputs.{nom}.priority").value),
                "timeout_s": float(self.get_parameter(f"inputs.{nom}.timeout_s").value),
                "twist": None,
                "stamp": 0.0,
                "count": 0,
            }

    # ── horloge et mesure ────────────────────────────────────────────────────

    def _now(self):
        """Horloge du nœud, en secondes : simulable dans les tests."""
        return self.get_clock().now().nanoseconds / 1e9

    def _noter_duree(self, debut):
        duree_ms = (perf_counter() - debut) * 1000.0
        maintenant = self._now()
        self._durees.append((maintenant, duree_ms))
        while self._durees and maintenant - self._durees[0][0] > FENETRE_MESURE_S:
            self._durees.pop(0)
        if duree_ms > GARDE_CALLBACK_MS:
            self.get_logger().warn(
                f"callback de {duree_ms:.1f} ms (> {GARDE_CALLBACK_MS:.0f} ms)")

    def max_callback_ms(self):
        return round(max((d for _, d in self._durees), default=0.0), 3)

    # ── entrées nommées ──────────────────────────────────────────────────────

    def _on_input(self, nom, msg):
        debut = perf_counter()
        entree = self._entrees[nom]
        entree["twist"] = (msg.linear.x, msg.linear.y, msg.angular.z)
        entree["stamp"] = self._now()
        entree["count"] += 1
        self._noter_duree(debut)

    def entree_retenue(self, maintenant=None):
        """Nom de l'entrée la plus prioritaire encore fraîche, ou None."""
        maintenant = self._now() if maintenant is None else maintenant
        choix = None
        for nom, entree in self._entrees.items():
            if entree["twist"] is None:
                continue
            if maintenant - entree["stamp"] > entree["timeout_s"]:
                continue
            if choix is None or entree["priority"] > self._entrees[choix]["priority"]:
                choix = nom
        return choix

    # ── arrêt d'urgence ──────────────────────────────────────────────────────

    def _on_estop(self, msg):
        debut = perf_counter()
        self._estop_dernier = bool(msg.data)
        if self._estop_dernier and not self._estop_latche:
            self._estop_latche = True
            self.get_logger().warn("e-stop recu : sortie annulee, verrou pose")
        self._noter_duree(debut)

    def _sur_reset_estop(self, _requete, reponse):
        if not self._estop_latche:
            reponse.success = False
            reponse.message = "aucun verrou actif"
        elif self._estop_dernier:
            reponse.success = False
            reponse.message = "signal d'e-stop encore actif : relacher le bouton d'abord"
        else:
            self._estop_latche = False
            reponse.success = True
            reponse.message = "verrou leve"
            self.get_logger().info("e-stop rearme par le tableau de bord")
        return reponse

    # ── capteurs ─────────────────────────────────────────────────────────────

    def on_scan(self, msg):
        debut = perf_counter()
        vals = [r for r, a in zip(msg.ranges, [msg.angle_min + msg.angle_increment * i
                                               for i in range(len(msg.ranges))])
                if abs(a) < math.radians(20) and msg.range_min < r < msg.range_max]
        if vals:
            self.front = min(vals)
        self.last_scan = self._now()
        self._noter_duree(debut)

    def on_volt(self, msg):
        debut = perf_counter()
        self.samples.append(float(msg.data))
        del self.samples[:-100]
        self._noter_duree(debut)

    def on_imu(self, msg):
        debut = perf_counter()
        self.roll, self.pitch = _rpy(msg.orientation)
        self.last_imu = self._now()
        self._noter_duree(debut)

    def on_arm(self, msg):
        debut = perf_counter()
        if len(msg.data) >= 2 and 0 <= msg.data[1] <= 180:
            self.servo2 = float(msg.data[1])
        self._noter_duree(debut)

    # ── boucle ───────────────────────────────────────────────────────────────

    def tick(self):
        debut = perf_counter()
        if not getattr(self, "_log_premier", False):
            self._log_premier = True
            self.get_logger().info("premier tick de l'arbitre")
        maintenant = self._now()
        self.age_scan = maintenant - self.last_scan if self.last_scan else 99.0
        self.age_imu = maintenant - self.last_imu if self.last_imu else 99.0

        # seuil de péremption configurable, sans toucher à decide()
        seuil = float(self.get_parameter("stale_s").value)
        age_scan = float("inf") if self.age_scan > seuil else self.age_scan
        age_imu = float("inf") if self.age_imu > seuil else self.age_imu

        source = self.entree_retenue(maintenant)
        self.cmd = self._entrees[source]["twist"] if source else (0.0, 0.0, 0.0)

        etat, (vx, vy, wz) = decide(self.cmd, self.front, self.roll, self.pitch,
                                    self.servo2, self.samples, age_scan, age_imu)
        if self._estop_latche:
            etat, (vx, vy, wz) = "ESTOP_LATCHED", (0.0, 0.0, 0.0)

        out = Twist()
        out.linear.x, out.linear.y, out.angular.z = vx, vy, wz
        self.pub_safe.publish(out)
        self.pub_hold.publish(Bool(data=etat != "OK"))
        self.derniere_sortie = (vx, vy, wz)

        self._noter_duree(debut)
        self.etat = {
            "state": etat,
            "source": source,
            "estop_latched": self._estop_latche,
            "max_callback_ms": self.max_callback_ms(),
        }
        self.pub_state.publish(String(data=json.dumps(self.etat, sort_keys=True)))

        self._n = getattr(self, "_n", 0) + 1
        if self._n % 100 == 0:
            self.get_logger().info(
                f"tick {self._n} etat={etat} source={source} cmd={vx:.3f}")

    def on_shutdown(self):
        """Laisse trois consignes nulles derrière soi.

        Le pilote n'a aucun arrêt sur silence (P01-M04) : le MCU garde la
        dernière trame reçue. Un contexte rclpy déjà fermé fait échouer
        `publish` ; on le journalise sans propager, l'arrêt doit aboutir.
        """
        for _ in range(3):
            try:
                self.pub_safe.publish(Twist())
            except Exception as exc:  # contexte invalidé par SIGINT/SIGTERM
                self.get_logger().warn(f"consigne nulle non publiee : {exc}")
                return
            time.sleep(0.02)


def main():
    rclpy.init(args=sys.argv[1:])
    node = Arbitrator()
    node.get_logger().info("arbitre pret, entree dans spin")
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.on_shutdown()
        node.destroy_node()
        rclpy.try_shutdown()   # SIGINT a déjà pu fermer le contexte
    return 0
