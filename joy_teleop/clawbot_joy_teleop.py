#!/usr/bin/env python3
"""Clawbot Joy Teleop — /joy → /cmd_vel + /servo_ctrl, piloté par config/manette.yaml.

Aucun index n'est codé ici. Le fichier de calibration nomme les entrées, mesure les
signes d'axe et fixe les zones mortes ; ce nœud ne fait que traduire des noms en
consignes ROS. Un pad remplacé ou recalibré ne demande aucune modification de code.

MAPPING LOGIQUE (les noms sont ceux du YAML)
  MOUVEMENT (mode 2, châssis mécanum)
    stick_droit_y   linear_x   — haut = avant
    stick_droit_x   linear_y   — droite = droite (y négatif)
    stick_gauche_x  angular_z  — droite = horaire (z négatif)
    plus            stop d'urgence

  BRAS (mode 1, incrément de arm_step par tick)
    ZL / ZR        servo 1 — base
    stick_droit_x  servo 6 — pince
    stick_droit_y  servo 4 — poignet
    stick_gauche_y servo 2 — épaule
    stick_gauche_x servo 3 — coude
    L / R          servo 5 — rotation pince
    croix_x / croix_y — déplacement châssis très lent

  BOUTONS
    A / B / Y — base du bras (0° / 90° / 180°), X — bascule caméra haute/basse

  Les SENS mécaniques du bras ne sont pas validés : à confirmer bras libre,
  opérateur présent.

PARAMÈTRES ROS 2
  manette_config  chemin du YAML de calibration
  linear_scale, angular_scale, arm_step, deadman_button, deadband
"""

import sys

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node

from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy
from std_msgs.msg import Int32MultiArray

from manette_config import ConfigInvalide, Manette, charger

CHEMIN_CONFIG = "/home/jetson/clawbot/config/manette.yaml"

# Limites hardware du châssis, identiques au hardware_service.
MAX_LINEAR_MS = 0.5
MAX_ANGULAR_RS = 1.5


def _clamp(valeur: float, mini: float, maxi: float) -> float:
    return max(mini, min(maxi, valeur))


#: Bornes des gains reglables a chaud. Un gain hors bornes est refuse, pas borne en
#: silence : l'operateur doit voir son reglage rejete (REQ-OPS-055).
GAINS_BORNES = {"linear_scale": (0.0, MAX_LINEAR_MS),
                "angular_scale": (0.0, MAX_ANGULAR_RS),
                "arm_step": (0.0, 30.0)}


def valider_gain(nom: str, valeur) -> tuple[bool, float | str]:
    """Rend (accepte, valeur ou raison du refus). Pure, donc testable sans ROS."""
    if nom not in GAINS_BORNES:
        return (True, valeur)
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return (False, f"{nom} : {valeur!r} n'est pas un nombre")
    if nombre != nombre or nombre in (float("inf"), float("-inf")):
        return (False, f"{nom} : valeur non finie")
    mini, maxi = GAINS_BORNES[nom]
    if not mini < nombre <= maxi:
        return (False, f"{nom} : {nombre} hors de ]{mini}, {maxi}]")
    return (True, nombre)


def consigne_vehicule(avant: float, droite: float, rotation: float,
                      lin_scale: float, ang_scale: float) -> tuple[float, float, float]:
    """Consigne (x, y, z) du mode vehicule, conventions REP-103.

    * `avant` > 0 avance ; `droite` > 0 va a droite ; `rotation` > 0 est un stick pousse
      a droite.
    * REP-103 : y positif = gauche, donc la translation laterale est inversee.
    * Le sens trigonometrique (anti-horaire) est un z positif : un stick de rotation pousse
      a gauche doit donc donner un z positif, d'ou l'inversion.
    """
    x = _clamp(avant * lin_scale, -MAX_LINEAR_MS, MAX_LINEAR_MS)
    y = _clamp(-droite * lin_scale, -MAX_LINEAR_MS, MAX_LINEAR_MS)
    z = _clamp(-rotation * ang_scale, -MAX_ANGULAR_RS, MAX_ANGULAR_RS)
    return (x, y, z)


class ClawbotJoyTeleop(Node):

    def __init__(self, config=None):
        super().__init__("clawbot_joy_teleop")

        self.declare_parameter("manette_config", CHEMIN_CONFIG)
        self.declare_parameter("linear_scale", MAX_LINEAR_MS)
        self.declare_parameter("angular_scale", MAX_ANGULAR_RS)
        self.declare_parameter("arm_step", 3.0)
        self.declare_parameter("deadman_button", -1)     # index, -1 = désactivé
        self.declare_parameter("deadband", 0.08)

        chemin = config if config is not None else self.get_parameter("manette_config").value
        try:
            self.manette: Manette = charger(chemin)
        except ConfigInvalide as err:
            # Aucun mapping par défaut : un pad mal mappé vaut moins qu'un pad absent.
            self.get_logger().error(f"configuration de manette refusée — {err}")
            raise SystemExit(1)

        self.lin_scale = float(self.get_parameter("linear_scale").value)
        self.ang_scale = float(self.get_parameter("angular_scale").value)
        self.arm_step = float(self.get_parameter("arm_step").value)
        self.deadman = int(self.get_parameter("deadman_button").value)
        self.deadband = float(self.get_parameter("deadband").value)
        # Sans ce rappel, `ros2 param set` afficherait la nouvelle valeur alors que le noeud
        # continuerait d'utiliser celle lue a la construction (REQ-OPS-055).
        self.add_on_set_parameters_callback(self._sur_parametre)

        self.arm_angles = {i: 90 for i in range(1, 6)}
        self.claw_angle = 90
        self.mode = 1                  # 1 : bras, 2 : véhicule
        self.camera_high = False
        self._btn_prev: list[int] = []
        self._forme_verifiee = False
        self._forme_invalide = False

        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.servo_pub = self.create_publisher(Int32MultiArray, "/servo_ctrl", 10)
        self.create_subscription(Joy, "/joy", self._joy_cb, 10)

        turbo = (self.manette.capacites.get("turbo") or {})
        if turbo.get("actif"):
            self.get_logger().warn(
                f"turbo armé sur le pad ({turbo.get('repetitions')} appuis en "
                f"{turbo.get('duree_mesure_s')} s sur {turbo.get('reference')}) — "
                f"les ordres seront répétés, à désactiver avant de piloter")

        self.get_logger().info(
            f"✅ ClawbotJoyTeleop prêt — {self.manette.chemin} "
            f"({len(self.manette.boutons)} boutons, {len(self.manette.axes)} axes), "
            f"deadman={self.deadman}, mode initial=bras")

    # ── accès nommés ─────────────────────────────────────────────────────────

    def _index(self, nom: str) -> int | None:
        return self.manette.bouton_ou_none(nom)

    def _presse(self, boutons: list[int], nom: str) -> bool:
        i = self._index(nom)
        return bool(boutons[i]) if i is not None and i < len(boutons) else False

    def _vient_d_etre_presse(self, boutons: list[int], nom: str) -> bool:
        i = self._index(nom)
        if i is None:
            return False
        actuel = bool(boutons[i]) if i < len(boutons) else False
        precedent = bool(self._btn_prev[i]) if i < len(self._btn_prev) else False
        return actuel and not precedent

    def _sur_parametre(self, parametres):
        """Applique a chaud les gains reglables ; refuse une valeur hors bornes."""
        resultat = SetParametersResult(successful=True)
        for parametre in parametres:
            accepte, valeur = valider_gain(parametre.name, parametre.value)
            if not accepte:
                resultat.successful = False
                resultat.reason = str(valeur)
                return resultat
            if parametre.name == "linear_scale":
                self.lin_scale = float(valeur)
            elif parametre.name == "angular_scale":
                self.ang_scale = float(valeur)
            elif parametre.name == "arm_step":
                self.arm_step = float(valeur)
        return resultat

    def _axe(self, axes: list[float], nom: str) -> float:
        """Valeur normalisée : positif = droite pour X, haut pour Y (sens du YAML)."""
        return self.manette.valeur(axes, nom)

    # ── servos ───────────────────────────────────────────────────────────────

    def _envoyer_servo(self, ident: int, angle: float) -> None:
        angle = int(_clamp(angle, 0, 180))
        self.arm_angles[ident] = angle
        msg = Int32MultiArray()
        msg.data = [ident, angle]
        self.servo_pub.publish(msg)
        self.get_logger().info(f"Servo {ident} → {angle}°")

    def _bouger_servo(self, ident: int, delta: float) -> None:
        self._envoyer_servo(ident, self.arm_angles.get(ident, 90) + delta)

    def _envoyer_pose(self, angles: list[float]) -> None:
        for i, a in enumerate(angles):
            self._envoyer_servo(i + 1, float(a))

    # ── callback ─────────────────────────────────────────────────────────────

    def _joy_cb(self, msg: Joy) -> None:
        axes = msg.axes
        boutons = list(msg.buttons)

        # Une manette à commutateur de mode change de descripteur HID : mêmes codes
        # numériques, boutons différents. Sans ce contrôle, un changement de mode
        # produit un pilotage faux sans le moindre message.
        if not self._forme_verifiee:
            try:
                self.manette.verifier_appareil(len(axes), len(boutons))
            except ConfigInvalide as err:
                self.get_logger().error(f"forme du pad incompatible — {err}")
                self._forme_invalide = True
            self._forme_verifiee = True
        if self._forme_invalide:
            self.cmd_vel_pub.publish(Twist())
            return

        if not self._btn_prev:
            self._btn_prev = [0] * len(boutons)

        # Deadman : s'il est armé sur un index, aucun mouvement sans lui.
        if self.deadman >= 0:
            arme = self.deadman < len(boutons) and bool(boutons[self.deadman])
            if not arme:
                self.cmd_vel_pub.publish(Twist())
                self._btn_prev = boutons[:]
                return

        if self._presse(boutons, "plus"):
            self.cmd_vel_pub.publish(Twist())
            self.get_logger().warn("⛔ STOP D'URGENCE")
            self._btn_prev = boutons[:]
            return

        if self._vient_d_etre_presse(boutons, "home"):
            self.mode = 2 if self.mode == 1 else 1
            self.get_logger().info(
                f"🔄 MODE → {'1: Bras' if self.mode == 1 else '2: Véhicule'}")
            self.cmd_vel_pub.publish(Twist())

        twist = Twist()

        if self.mode == 1:
            if self._presse(boutons, "ZL"):
                self._bouger_servo(1, -self.arm_step)
            if self._presse(boutons, "ZR"):
                self._bouger_servo(1, self.arm_step)

            pince = self._axe(axes, "stick_droit_x")
            if pince != 0.0:
                self._bouger_servo(6, pince * self.arm_step * 2.0)

            poignet = self._axe(axes, "stick_droit_y")
            if poignet != 0.0:
                self._bouger_servo(4, poignet * self.arm_step)

            epaule = self._axe(axes, "stick_gauche_y")
            if epaule != 0.0:
                self._bouger_servo(2, epaule * self.arm_step)

            coude = self._axe(axes, "stick_gauche_x")
            if coude != 0.0:
                self._bouger_servo(3, coude * self.arm_step)

            if self._presse(boutons, "L"):
                self._bouger_servo(5, self.arm_step)
            if self._presse(boutons, "R"):
                self._bouger_servo(5, -self.arm_step)

            avant = self._axe(axes, "croix_y")
            droite = self._axe(axes, "croix_x")
            twist.linear.x = _clamp(avant * self.lin_scale * 0.2, -MAX_LINEAR_MS, MAX_LINEAR_MS)
            twist.linear.y = _clamp(-droite * self.lin_scale * 0.2, -MAX_LINEAR_MS, MAX_LINEAR_MS)
            twist.angular.z = 0.0
            self.cmd_vel_pub.publish(twist)

        else:
            # Stick gauche = deplacement, stick droit = rotation (REQ-OPS-056).
            avant = self._axe(axes, "stick_gauche_y")
            droite = self._axe(axes, "stick_gauche_x")
            rotation = self._axe(axes, "stick_droit_x")

            twist.linear.x, twist.linear.y, twist.angular.z = consigne_vehicule(
                avant, droite, rotation, self.lin_scale, self.ang_scale)
            self.cmd_vel_pub.publish(twist)

            if self._vient_d_etre_presse(boutons, "Y"):
                self._envoyer_servo(1, 180)
            if self._vient_d_etre_presse(boutons, "A"):
                self._envoyer_servo(1, 0)
            if self._vient_d_etre_presse(boutons, "B"):
                self._envoyer_servo(1, 90)

            if self._vient_d_etre_presse(boutons, "X"):
                self.camera_high = not self.camera_high
                if self.camera_high:
                    self._envoyer_pose([90, 90, 90, 0, 90])
                    self.get_logger().info("📷 Caméra : HAUTE")
                else:
                    self._envoyer_pose([90, 180, 0, 0, 90])
                    self.get_logger().info("📷 Caméra : BASSE")

        self._btn_prev = boutons[:]


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ClawbotJoyTeleop()
    except SystemExit:
        rclpy.try_shutdown()
        return 1
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cmd_vel_pub.publish(Twist())
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
