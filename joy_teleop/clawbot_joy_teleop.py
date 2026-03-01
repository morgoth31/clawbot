    #!/usr/bin/env python3
"""
Clawbot Joy Teleop — Nintendo Switch Pro Controller (ou manette générique)
════════════════════════════════════════════════════════════════════════════

MAPPING PAR DÉFAUT (Pro Controller via hid-nintendo ou générique compatible):

  MOUVEMENT (chassis mécanum)
  ┌─────────────────┬──────────────────────────────────────────┐
  │ Stick gauche Y  │ linear_x  (avant / arrière)              │
  │ Stick gauche X  │ linear_y  (strafe gauche / droite)       │
  │ Stick droit  X  │ angular_z (rotation)                     │
  │ ZR  (hold)      │ Deadman switch (obligatoire pour bouger) │
  │ Plus (+)        │ Stop d'urgence                           │
  └─────────────────┴──────────────────────────────────────────┘

  BRAS (servos 1-5, incrément par tick)
  ┌─────────────────┬──────────────────────────────────────────┐
  │ D-pad Y         │ Servo 1 — base rotation                  │
  │ D-pad X         │ Servo 2 — épaule                         │
  │ Stick droit Y   │ Servo 3 — coude                          │
  │ L (shoulder)    │ Servo 4 — poignet -                      │
  │ R (shoulder)    │ Servo 4 — poignet +                      │
  │ ZL (hold)       │ Servo 5 — rotation poignet -             │
  │   + D-pad X     │   (ZL modifie D-pad X → servo 5)        │
  └─────────────────┴──────────────────────────────────────────┘

  PINCE & POSES
  ┌─────────────────┬──────────────────────────────────────────┐
  │ A               │ Pince ouverte (servo 6 = 0°)             │
  │ B               │ Pince fermée  (servo 6 = 180°)           │
  │ Y               │ Pose sécurisée (anti-collision)          │
  │ X               │ Pose détendue (90° partout)              │
  │ Minus (-)       │ Reset bras — tout à 90°                  │
  └─────────────────┴──────────────────────────────────────────┘

AJUSTEMENTS RAPIDES via paramètres ROS2:
  linear_scale    — vitesse max linéaire (défaut: 0.06 m/s)
  angular_scale   — vitesse max angulaire (défaut: 0.25 rad/s)
  arm_step        — degrés par tick pour le bras (défaut: 3°)
  deadman_button  — index du bouton deadman (défaut: 7 = ZR)
  invert_ly       — inverser axe stick gauche Y (défaut: true)
  invert_ry       — inverser axe stick droit  Y (défaut: true)
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist
from std_msgs.msg import Int32MultiArray

# ── Limites hardware ──────────────────────────────────────────────────────────
MAX_LINEAR_MS  = 0.5    # m/s   — identique au hardware_service
MAX_ANGULAR_RS = 1.5    # rad/s

SAFE_POSE    = [90, 130, 10, 60, 90]   # anti-collision
NEUTRAL_POSE = [90,  90, 90, 90, 90]   # bras détendu

# ── Mapping axes ─────────────────────────────────────────────────────────────
# Détecté via jstest pour Nintendo Switch Pro Controller (USB via hid_nintendo)
# 6 axes: X, Y, Rx, Ry, Hat0X, Hat0Y
AX_LX = 0   # Stick gauche X
AX_LY = 1   # Stick gauche Y
AX_RX = 2   # Stick droit  X
AX_RY = 3   # Stick droit  Y
AX_DX = 4   # D-pad X (FX)
AX_DY = 5   # D-pad Y (FY)

# ── Mapping boutons ───────────────────────────────────────────────────────────
# Détecté via jstest: 14 boutons
# BtnA, BtnB, BtnX, BtnY, BtnZ, BtnTL, BtnTR, BtnTL2, BtnTR2, BtnSelect, BtnStart, BtnMode, BtnThumbL, BtnThumbR
BTN_B      = 0
BTN_A      = 1
BTN_X      = 2
BTN_Y      = 3
BTN_O      = 4
BTN_L      = 5
BTN_R      = 6
BTN_ZL     = 7
BTN_ZR     = 8
BTN_MINUS  = 9   # -
BTN_PLUS   = 10  # +
BTN_HOME   = 11  # Home
BTN_LS     = 12  # JL
BTN_RS     = 13  # JR


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class ClawbotJoyTeleop(Node):

    def __init__(self):
        super().__init__("clawbot_joy_teleop")

        # ── Paramètres ────────────────────────────────────────────────────────
        self.declare_parameter("linear_scale",   MAX_LINEAR_MS)
        self.declare_parameter("angular_scale",  MAX_ANGULAR_RS)
        self.declare_parameter("arm_step",       3.0)        # degrés / tick
        self.declare_parameter("deadman_button", BTN_ZR)     # tenir ZR (btn 9) pour bouger
        self.declare_parameter("invert_ly",      True)       # axes Y souvent inversés
        self.declare_parameter("invert_ry",      True)
        self.declare_parameter("deadband",       0.08)       # seuil stick mort

        self.lin_scale  = self.get_parameter("linear_scale").value
        self.ang_scale  = self.get_parameter("angular_scale").value
        self.arm_step   = self.get_parameter("arm_step").value
        self.deadman    = self.get_parameter("deadman_button").value
        self.inv_ly     = self.get_parameter("invert_ly").value
        self.inv_ry     = self.get_parameter("invert_ry").value
        self.deadband   = self.get_parameter("deadband").value

        # ── État interne ─────────────────────────────────────────────────────
        # Angles courants du bras (IDs 1-5) — -1 = inconnu
        self.arm_angles = {i: 90 for i in range(1, 6)}
        self.claw_angle = 90   # servo 6
        
        # Modes de fonctionnement
        self.mode = 1          # 1: Pilotage du bras, 2: Pilotage du robot
        self.camera_high = False

        # Anti-répétition boutons
        self._btn_prev: list[int] = []

        # ── Publishers ────────────────────────────────────────────────────────
        self.cmd_vel_pub = self.create_publisher(Twist,           "/cmd_vel",    10)
        self.servo_pub   = self.create_publisher(Int32MultiArray, "/servo_ctrl", 10)

        # ── Subscriber ───────────────────────────────────────────────────────
        self.create_subscription(Joy, "/joy", self._joy_cb, 10)

        self.get_logger().info(
            f"✅ ClawbotJoyTeleop ready — deadman=BTN[{self.deadman}] (ZR par défaut)\n"
            f"   linear={self.lin_scale} m/s  angular={self.ang_scale} rad/s  "
            f"arm_step={self.arm_step}°"
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ax(self, axes: list, idx: int, invert: bool = False) -> float:
        """Lire un axe avec deadband et inversion optionnelle."""
        if idx >= len(axes):
            return 0.0
        v = axes[idx] * (-1.0 if invert else 1.0)
        return v if abs(v) > self.deadband else 0.0

    def _btn(self, buttons: list, idx: int) -> bool:
        """Lire un bouton."""
        return bool(buttons[idx]) if idx < len(buttons) else False

    def _btn_just_pressed(self, buttons: list, idx: int) -> bool:
        """True seulement au premier tick où le bouton est enfoncé."""
        cur  = self._btn(buttons, idx)
        prev = bool(self._btn_prev[idx]) if idx < len(self._btn_prev) else False
        return cur and not prev

    def _send_servo(self, servo_id: int, angle: float) -> None:
        """Clamp et publie une commande servo."""
        angle = int(_clamp(angle, 0, 180))
        self.arm_angles[servo_id] = angle
        msg = Int32MultiArray()
        msg.data = [servo_id, angle]
        self.servo_pub.publish(msg)
        self.get_logger().info(f"Servo {servo_id} → {angle}°")

    def _send_arm_pose(self, angles: list) -> None:
        """Envoyer tous les servos 1-5 vers une pose."""
        for i, a in enumerate(angles):
            self._send_servo(i + 1, float(a))
        self.get_logger().info(f"Pose → {angles}")

    def _move_servo(self, servo_id: int, delta: float) -> None:
        """Incrémenter un servo de delta degrés."""
        new_angle = self.arm_angles.get(servo_id, 90) + delta
        self._send_servo(servo_id, new_angle)

    # ── Callback principal ────────────────────────────────────────────────────

    def _joy_cb(self, msg: Joy) -> None:
        axes    = msg.axes
        buttons = list(msg.buttons)

        # Initialiser prev au premier message
        if not self._btn_prev:
            self._btn_prev = [0] * len(buttons)

        # ── STOP D'URGENCE — Plus (+) ─────────────────────────────────────────
        if self._btn(buttons, BTN_PLUS):
            self.cmd_vel_pub.publish(Twist())
            self.get_logger().warn("⛔ STOP D'URGENCE")
            self._btn_prev = buttons[:]
            return
            
        # ── CHANGEMENT DE MODE — Home ─────────────────────────────────────────
        if self._btn_just_pressed(buttons, BTN_HOME):
            self.mode = 2 if self.mode == 1 else 1
            mode_name = "1: Bras" if self.mode == 1 else "2: Véhicule"
            self.get_logger().info(f"🔄 MODE CHANGÉ → {mode_name}")
            # Stop vehicle when changing mode
            self.cmd_vel_pub.publish(Twist())

        twist = Twist()

        if self.mode == 1:
            # ── MODE 1 : Pilotage du bras ─────────────────────────────────────
            # Bras
            zl = self._btn(buttons, BTN_ZL)
            zr = self._btn(buttons, BTN_ZR)
            if zl: self._move_servo(1, -self.arm_step)   # ZL rotate gauche/droite
            if zr: self._move_servo(1, self.arm_step)    # ZR rotate gauche/droite
            
            rx = self._ax(axes, AX_RX)
            if rx != 0.0:
                # Ouverture/fermeture de la pince (Servo 6)
                # RX varie de -1 à 1. On peut incrémenter de arm_step selon le signe
                self._move_servo(6, -rx * self.arm_step * 2.0)
                
            ry = self._ax(axes, AX_RY, invert=self.inv_ry)
            if ry != 0.0:
                self._move_servo(4, ry * self.arm_step)  # RY -> servo 4
                
            ly = self._ax(axes, AX_LY, invert=self.inv_ly)
            if ly != 0.0:
                self._move_servo(2, ly * self.arm_step)  # LY -> servo 2
                
            lx = self._ax(axes, AX_LX)
            if lx != 0.0:
                self._move_servo(3, lx * self.arm_step)  # LX -> servo 3
                
            l = self._btn(buttons, BTN_L)
            r = self._btn(buttons, BTN_R)
            if l: self._move_servo(5, self.arm_step)     # L rotate pince
            if r: self._move_servo(5, -self.arm_step)    # R rotate pince
            
            # Robot très lent (utiliser boutons D-pad reconnus comme axes FX/FY)
            fx = self._ax(axes, AX_DX)  # D-pad X (FX)
            fy = self._ax(axes, AX_DY, invert=True)  # D-pad Y (FY) inversé sur hid_nintendo souvent
            
            twist.linear.x  = _clamp(fy * self.lin_scale * 0.2, -MAX_LINEAR_MS, MAX_LINEAR_MS)
            twist.linear.y  = _clamp(fx * self.lin_scale * 0.2, -MAX_LINEAR_MS, MAX_LINEAR_MS)
            twist.angular.z = 0.0
            
            self.cmd_vel_pub.publish(twist)

        elif self.mode == 2:
            # ── MODE 2 : Pilotage du robot ────────────────────────────────────
            ry = self._ax(axes, AX_RY, invert=self.inv_ry)
            rx = self._ax(axes, AX_RX)
            lx = self._ax(axes, AX_LX)
            
            twist.linear.x  = _clamp(ry * self.lin_scale, -MAX_LINEAR_MS, MAX_LINEAR_MS)
            twist.linear.y  = _clamp(rx * self.lin_scale, -MAX_LINEAR_MS, MAX_LINEAR_MS)
            twist.angular.z = _clamp(lx * self.ang_scale, -MAX_ANGULAR_RS, MAX_ANGULAR_RS)
            
            self.cmd_vel_pub.publish(twist)
            
            # Rotation du bras (servo 1)
            if self._btn_just_pressed(buttons, BTN_Y):
                self._send_servo(1, 180)  # Gauche
            if self._btn_just_pressed(buttons, BTN_A):
                self._send_servo(1, 0)    # Droite
            if self._btn_just_pressed(buttons, BTN_B):
                self._send_servo(1, 90)   # Avant
                
            # Switch position caméra (X)
            if self._btn_just_pressed(buttons, BTN_X):
                self.camera_high = not self.camera_high
                if self.camera_high:
                    # Position haute
                    self._send_arm_pose([90, 90, 90, 0, 90])
                    self.get_logger().info("📷 Caméra: HAUTE")
                else:
                    # Position basse
                    self._send_arm_pose([90, 180, 0, 0, 90])
                    self.get_logger().info("📷 Caméra: BASSE")

        self._btn_prev = buttons[:]


def main(args=None):
    rclpy.init(args=args)
    node = ClawbotJoyTeleop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cmd_vel_pub.publish(Twist())   # stop au shutdown
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
