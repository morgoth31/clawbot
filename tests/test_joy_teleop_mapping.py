"""Manette : mapping mesuré, choix du périphérique, et absence de dépendance à SDL.

Ces tests protègent les trois choses qui ont réellement cassé le 2026-11-15 et
qui casseraient en silence si on y touchait :

  1. Les gâchettes ne sont pas dans l'ordre « L, R, ZL, ZR » mais ZL, ZR, L, R.
     Un code qui vise ZR en croyant viser l'index 8 commande L : sur un deadman,
     cela veut dire aucune protection.
  2. Les axes Y valent +1 vers le haut. Une inversion héritée fait reculer le
     robot quand on pousse le stick vers l'avant.
  3. Le pad et son IMU exposent le même nom. Le choix du périphérique doit donc
     se faire sur le nom du nœud d'entrée, pas sur un index SDL.

Aucun test ici ne déplace le robot : le nœud teleop est instancié en domaine 99,
où rien n'écoute /cmd_vel ni /servo_ctrl.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "joy_teleop"))

os.environ["ROS_DOMAIN_ID"] = "98"   # 98 : isolé de la simulation (99) et du robot (28)

rclpy = pytest.importorskip("rclpy")
from geometry_msgs.msg import Twist          # noqa: E402
from sensor_msgs.msg import Joy              # noqa: E402
from std_msgs.msg import Int32MultiArray     # noqa: E402

import clawbot_joy_teleop as teleop          # noqa: E402


# ── Fixture : nœud teleop + publication synthétique de /joy ──────────────────

class Banc:
    def __init__(self):
        self.node = teleop.ClawbotJoyTeleop()
        self.node.get_logger().set_level(40)   # WARN : le nœud journalise chaque servo
        self.pub = self.node.create_publisher(Joy, "/joy", 10)
        self.twists: list[Twist] = []
        self.servos: list[list[int]] = []
        self.node.create_subscription(Twist, "/cmd_vel", self._sur_twist, 10)
        self.node.create_subscription(Int32MultiArray, "/servo_ctrl", self._sur_servo, 10)

    def _sur_twist(self, msg):
        self.twists.append(msg)

    def _sur_servo(self, msg):
        self.servos.append(list(msg.data))

    def envoyer(self, axes=None, boutons=None, duree=0.4):
        """Publie un état /joy pendant `duree` (le nœud traite chaque message)."""
        axes = axes if axes is not None else [0.0] * 6
        boutons = boutons if boutons is not None else [0] * 14
        fin = time.time() + duree
        while time.time() < fin:
            msg = Joy()
            msg.axes = [float(a) for a in axes]
            msg.buttons = [int(b) for b in boutons]
            self.pub.publish(msg)
            rclpy.spin_once(self.node, timeout_sec=0.02)

    def vider(self, duree=0.3):
        """Vide les listes APRÈS avoir laissé arriver les messages déjà en vol.

        Sans cette purge, les messages du scénario précédent arrivent pendant le
        suivant et le test attribue à un bouton l'effet d'un autre.
        """
        fin = time.time() + duree
        while time.time() < fin:
            rclpy.spin_once(self.node, timeout_sec=0.02)
        self.twists.clear()
        self.servos.clear()

    def fermer(self):
        self.node.destroy_node()


@pytest.fixture()
def banc():
    rclpy.init()
    b = Banc()
    yield b
    b.fermer()
    rclpy.try_shutdown()


# ── Constantes : la mesure, pas la tradition ─────────────────────────────────

def test_indices_gachettes():
    assert teleop.BTN_ZL == 5
    assert teleop.BTN_ZR == 6
    assert teleop.BTN_L == 7
    assert teleop.BTN_R == 8
    assert teleop.BTN_A == 1 and teleop.BTN_B == 0


def test_signes_axes_mesures():
    """Signes relevés sur la source jsdev : X positive à droite, Y négative en haut.

    Le paquet `joy` (SDL) inversait les deux. Une table relevée à travers SDL donne
    donc les signes opposés, et un code qui s'y fie commande la marche arrière.
    """
    source = (RACINE / "joy_teleop" / "clawbot_joy_teleop.py").read_text()
    assert "haut   = -1" in source          # AX_LY, AX_RY, AX_DY
    assert "droite = +1" in source          # AX_LX, AX_RX, AX_DX
    assert "return -self._brut(axes, idx)" in source   # _haut inverse le Y


# ── Sélection du périphérique ────────────────────────────────────────────────

def test_peripherique_choisi_nest_pas_l_imu():
    pytest.importorskip("rclpy")
    import js_joy_source

    manettes = js_joy_source.lister_manettes()
    if not manettes:
        pytest.skip("aucune manette branchée")
    chemin, nom = manettes[0]
    assert "IMU" not in nom.upper()
    assert chemin.startswith("/dev/input/js")


def test_source_sans_sdl():
    """La source ne doit pas dépendre du paquet joy (SDL) ni de SDL lui-même."""
    source = (RACINE / "joy_teleop" / "js_joy_source.py").read_text()
    assert "import rclpy" in source
    assert "import sdl" not in source.lower()
    assert "pygame" not in source.lower()
    lancement = (RACINE / "joy_teleop" / "joy_teleop_launch.py").read_text()
    assert 'package="joy"' not in lancement
    assert "js_joy_source.py" in lancement


def test_argument_lancement_jamais_vide():
    """`-p device_path:=` vide fait mourir le nœud au démarrage (rcl refuse).

    Mesuré le 2026-11-15 : RCLError « Couldn't parse parameter override rule ».
    Le défaut doit donc être une valeur exploitable, et le nœud doit la traiter
    comme « détection automatique ».
    """
    lancement = (RACINE / "joy_teleop" / "joy_teleop_launch.py").read_text()
    assert 'DeclareLaunchArgument("device_path",    default_value="auto"' in lancement
    source = (RACINE / "joy_teleop" / "js_joy_source.py").read_text()
    assert 'chemin == "auto"' in source


def test_source_reutilise_le_lecteur():
    """La source ne doit pas redécoder js_event : js_lecteur en est l'unique copie."""
    source = (RACINE / "joy_teleop" / "js_joy_source.py").read_text()
    assert "from js_lecteur import LecteurJs" in source
    assert "struct.unpack" not in source


# ── Comportement en mode véhicule ────────────────────────────────────────────

def _passer_mode_vehicule(banc):
    banc.envoyer(boutons=[0] * 14, duree=0.1)
    boutons = [0] * 14
    boutons[teleop.BTN_HOME] = 1
    banc.envoyer(boutons=boutons, duree=0.2)
    banc.envoyer(boutons=[0] * 14, duree=0.1)


def test_stick_droit_haut_avance(banc):
    _passer_mode_vehicule(banc)
    banc.vider()
    axes = [0.0] * 6
    axes[teleop.AX_RY] = -1.0          # mesuré : haut = -1 sur la source jsdev
    banc.envoyer(axes=axes)
    assert banc.twists, "aucun /cmd_vel publié"
    assert banc.twists[-1].linear.x > 0.0


def test_stick_droit_bas_recule(banc):
    _passer_mode_vehicule(banc)
    banc.vider()
    axes = [0.0] * 6
    axes[teleop.AX_RY] = +1.0          # bas = +1
    banc.envoyer(axes=axes)
    assert banc.twists[-1].linear.x < 0.0


def test_stick_droit_droite_strafe_a_droite(banc):
    _passer_mode_vehicule(banc)
    banc.vider()
    axes = [0.0] * 6
    axes[teleop.AX_RX] = +1.0          # mesuré : droite = +1
    banc.envoyer(axes=axes)
    assert banc.twists[-1].linear.y < 0.0   # REP-103 : y négatif = droite


def test_stick_gauche_droite_tourne_a_droite(banc):
    _passer_mode_vehicule(banc)
    banc.vider()
    axes = [0.0] * 6
    axes[teleop.AX_LX] = +1.0          # mesuré : droite = +1
    banc.envoyer(axes=axes)
    assert banc.twists[-1].angular.z < 0.0  # z négatif = horaire = droite


# ── Comportement en mode bras ────────────────────────────────────────────────

def test_zr_ne_commande_pas_le_meme_servo_que_l(banc):
    """ZR et L doivent agir sur deux servos différents (1 et 5)."""
    banc.envoyer(boutons=[0] * 14, duree=0.1)

    boutons = [0] * 14
    boutons[teleop.BTN_ZR] = 1
    banc.vider()
    banc.envoyer(boutons=boutons, duree=0.3)
    servos_zr = [s for s in banc.servos if s]

    boutons = [0] * 14
    boutons[teleop.BTN_L] = 1
    banc.vider()
    banc.envoyer(boutons=boutons, duree=0.3)
    servos_l = [s for s in banc.servos if s]

    assert servos_zr and servos_l
    assert {s[0] for s in servos_zr} == {1}, f"ZR doit viser le servo 1, vu {servos_zr[:3]}"
    assert {s[0] for s in servos_l} == {5}, f"L doit viser le servo 5, vu {servos_l[:3]}"


def test_plus_remet_la_consigne_a_zero(banc):
    _passer_mode_vehicule(banc)
    axes = [0.0] * 6
    axes[teleop.AX_RY] = 1.0
    banc.envoyer(axes=axes, duree=0.3)
    boutons = [0] * 14
    boutons[teleop.BTN_PLUS] = 1
    banc.vider()
    banc.envoyer(axes=axes, boutons=boutons, duree=0.3)
    assert banc.twists[-1].linear.x == 0.0
    assert banc.twists[-1].angular.z == 0.0
