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

        self.arm_angles = {i: 90 for i in range(1, 6)}
        self.claw_angle = 90
        self.mode = 1                  # 1 : bras, 2 : véhicule
        self.camera_high = False
        self._btn_prev: list[int] = []

        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.servo_pub = self.create_publisher(Int32MultiArray, "/servo_ctrl", 10)
        self.create_subscription(Joy, "/joy", self._joy_cb, 10)

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
            avant = self._axe(axes, "stick_droit_y")
            droite = self._axe(axes, "stick_droit_x")
            rotation = self._axe(axes, "stick_gauche_x")

            twist.linear.x = _clamp(avant * self.lin_scale, -MAX_LINEAR_MS, MAX_LINEAR_MS)
            # REP-103 : y positif = gauche, donc on inverse
            twist.linear.y = _clamp(-droite * self.lin_scale, -MAX_LINEAR_MS, MAX_LINEAR_MS)
            # z positif = antihoraire, donc on inverse pour tourner à droite
            twist.angular.z = _clamp(-rotation * self.ang_scale, -MAX_ANGULAR_RS, MAX_ANGULAR_RS)
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
