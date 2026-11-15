"""Manette : la configuration YAML pilote le teleop, plus aucune constante.

Trois pièges mesurés le 2026-11-15 sont couverts ici :

  1. La numérotation des boutons dépend de la couche qui lit (SDL ≠ jsdev). Le
     teleop ne connaît donc plus d'index : seulement des noms, résolus par
     `config/manette.yaml`.
  2. Les axes Y sont négatifs vers le haut sur jsdev ; SDL inversait les deux. Le
     sens vient de la calibration, pas d'une convention supposée.
  3. Un pad mal mappé vaut moins qu'un pad absent : sans YAML valide, le nœud
     refuse de démarrer.

Aucun test ici ne déplace le robot : le nœud est instancié en domaine 98, où rien
n'écoute /cmd_vel ni /servo_ctrl.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "joy_teleop"))

os.environ["ROS_DOMAIN_ID"] = "98"   # isolé de la simulation (99) et du robot (28)

rclpy = pytest.importorskip("rclpy")
from geometry_msgs.msg import Twist          # noqa: E402
from sensor_msgs.msg import Joy              # noqa: E402
from std_msgs.msg import Int32MultiArray     # noqa: E402

import clawbot_joy_teleop as teleop          # noqa: E402

FIXTURE = RACINE / "tests" / "fixtures" / "manette_test.yaml"


# ── Banc : nœud réel + publication synthétique de /joy ──────────────────────

class Banc:
    def __init__(self):
        self.node = teleop.ClawbotJoyTeleop(config=FIXTURE)
        self.node.get_logger().set_level(40)
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
        """Laisse arriver les messages en vol AVANT de purger les listes."""
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


# ── La configuration décide ─────────────────────────────────────────────────

def test_les_noms_resolvent_les_index_du_yaml():
    from manette_config import charger
    m = charger(FIXTURE)
    assert m.bouton("home") == 11
    assert m.bouton("ZR") == 8
    assert m.bouton("M1") == m.bouton("A")      # alias


def test_sans_configuration_le_noeud_refuse_de_demarrer(tmp_path):
    """Un pad mal mappé vaut moins qu'un pad absent."""
    rclpy.init()
    try:
        with pytest.raises(SystemExit) as err:
            teleop.ClawbotJoyTeleop(config=tmp_path / "absent.yaml")
        assert err.value.code == 1
    finally:
        rclpy.try_shutdown()


def test_aucune_table_d_indices_dans_le_noeud():
    source = (RACINE / "joy_teleop" / "clawbot_joy_teleop.py").read_text()
    assert "BTN_HOME" not in source
    assert "AX_LX" not in source
    assert "manette_config" in source


# ── Sélection du périphérique et source ─────────────────────────────────────

def test_peripherique_choisi_nest_pas_l_imu():
    import js_joy_source

    manettes = js_joy_source.lister_manettes()
    if not manettes:
        pytest.skip("aucune manette branchée")
    chemin, nom = manettes[0]
    assert "IMU" not in nom.upper()
    assert chemin.startswith("/dev/input/js")


def test_source_sans_sdl():
    source = (RACINE / "joy_teleop" / "js_joy_source.py").read_text()
    assert "import rclpy" in source
    assert "import sdl" not in source.lower()
    assert "pygame" not in source.lower()
    lancement = (RACINE / "joy_teleop" / "joy_teleop_launch.py").read_text()
    assert 'package="joy"' not in lancement
    assert "js_joy_source.py" in lancement


def test_source_reutilise_le_lecteur():
    source = (RACINE / "joy_teleop" / "js_joy_source.py").read_text()
    assert "from js_lecteur import LecteurJs" in source
    assert "struct.unpack" not in source


def test_argument_lancement_jamais_vide():
    """`-p device_path:=` vide fait mourir le nœud au démarrage (rcl refuse)."""
    lancement = (RACINE / "joy_teleop" / "joy_teleop_launch.py").read_text()
    assert 'DeclareLaunchArgument("device_path",    default_value="auto"' in lancement
    source = (RACINE / "joy_teleop" / "js_joy_source.py").read_text()
    assert 'chemin == "auto"' in source


# ── Mode véhicule ───────────────────────────────────────────────────────────

def _passer_mode_vehicule(banc):
    banc.envoyer(boutons=[0] * 14, duree=0.1)
    boutons = [0] * 14
    boutons[11] = 1                      # home
    banc.envoyer(boutons=boutons, duree=0.2)
    banc.envoyer(boutons=[0] * 14, duree=0.1)


def test_stick_droit_haut_avance(banc):
    _passer_mode_vehicule(banc)
    banc.vider()
    axes = [0.0] * 6
    axes[3] = -1.0                       # mesuré : haut = -1 sur jsdev
    banc.envoyer(axes=axes)
    assert banc.twists, "aucun /cmd_vel publié"
    assert banc.twists[-1].linear.x > 0.0


def test_stick_droit_bas_recule(banc):
    _passer_mode_vehicule(banc)
    banc.vider()
    axes = [0.0] * 6
    axes[3] = 1.0
    banc.envoyer(axes=axes)
    assert banc.twists[-1].linear.x < 0.0


def test_stick_droit_droite_strafe_a_droite(banc):
    _passer_mode_vehicule(banc)
    banc.vider()
    axes = [0.0] * 6
    axes[2] = 1.0                        # mesuré : droite = +1
    banc.envoyer(axes=axes)
    assert banc.twists[-1].linear.y < 0.0    # REP-103 : y négatif = droite


def test_stick_gauche_droite_tourne_a_droite(banc):
    _passer_mode_vehicule(banc)
    banc.vider()
    axes = [0.0] * 6
    axes[0] = 1.0
    banc.envoyer(axes=axes)
    assert banc.twists[-1].angular.z < 0.0   # z négatif = horaire = droite


# ── Mode bras ───────────────────────────────────────────────────────────────

def test_zr_ne_commande_pas_le_meme_servo_que_l(banc):
    """ZR (8) et L (5) doivent agir sur deux servos différents (1 et 5)."""
    banc.envoyer(boutons=[0] * 14, duree=0.1)

    boutons = [0] * 14
    boutons[8] = 1                       # ZR
    banc.vider()
    banc.envoyer(boutons=boutons, duree=0.3)
    servos_zr = [s for s in banc.servos if s]

    boutons = [0] * 14
    boutons[5] = 1                       # L
    banc.vider()
    banc.envoyer(boutons=boutons, duree=0.3)
    servos_l = [s for s in banc.servos if s]

    assert servos_zr and servos_l
    assert {s[0] for s in servos_zr} == {1}, f"ZR doit viser le servo 1, vu {servos_zr[:3]}"
    assert {s[0] for s in servos_l} == {5}, f"L doit viser le servo 5, vu {servos_l[:3]}"


def test_plus_remet_la_consigne_a_zero(banc):
    _passer_mode_vehicule(banc)
    axes = [0.0] * 6
    axes[3] = -1.0
    banc.envoyer(axes=axes, duree=0.3)
    boutons = [0] * 14
    boutons[10] = 1                       # +
    banc.vider()
    banc.envoyer(axes=axes, boutons=boutons, duree=0.3)
    assert banc.twists[-1].linear.x == 0.0
    assert banc.twists[-1].angular.z == 0.0
