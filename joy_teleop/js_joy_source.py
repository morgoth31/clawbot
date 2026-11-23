#!/usr/bin/env python3
"""js_joy_source — publie sensor_msgs/Joy depuis /dev/input/jsN, sans SDL.

Pourquoi ce nœud existe
═══════════════════════
Le paquet ROS `joy` passe par SDL. Sur ce poste, la manette Nintendo expose DEUX
nœuds d'entrée portant le même nom SDL (« Nintendo Switch Pro Controller ») : le
pad et son IMU. L'index SDL n'est pas stable — après une reconnexion Bluetooth, la
manette est passée de l'index 0 à l'index 1 — et `device_name` ne discrimine pas
puisque les deux entrées portent le même nom.

Conséquence mesurée le 2026-11-15 : `joy_node` ouvrait l'IMU et publiait 6 axes
avec zéro bouton, sans erreur. Ce nœud supprime la question : il choisit le nœud
dont le nom de périphérique n'est pas un capteur inertiel.

    /proc/bus/input/devices → « Nintendo Switch Pro Controller »      → js0  ← choisi
                            → « Nintendo Switch Pro Controller IMU »  → js1  ← écarté

Le décodage de `struct js_event` vit dans `js_lecteur.py`, partagé avec la
calibration : ce fichier ne contient que la publication ROS.

Paramètres
══════════
  device_path  chemin forcé, ou « auto » (détection, IMU exclu)
  rate         cadence de publication en Hz (défaut 20.0)
  deadzone     seuil de zone morte sur les axes (défaut 0.05)

Sortie : code 1 si le périphérique disparaît, pour que systemd relance l'unité.
"""

import os
import sys
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy

from js_lecteur import LecteurJs, lister_manettes


def choisir_pad(entrees: list[tuple[str, str]]) -> tuple[str, str] | None:
    """Rend (chemin, nom) de la premiere manette non inertielle, ou None.

    Une reconnexion Bluetooth recree le peripherique, et son numero peut changer : js0
    devient js1. La manette expose deux interfaces, dont une inertielle (IMU) qu'il faut
    ecarter. Pure, donc testable sans materiel.
    """
    for chemin, nom in entrees:
        if "IMU" not in nom.upper():
            return (chemin, nom)
    return None


class JsJoySource(Node):

    def __init__(self):
        super().__init__("js_joy_source")

        self.declare_parameter("device_path", "auto")
        self.declare_parameter("rate", 20.0)
        self.declare_parameter("deadzone", 0.05)

        self.rate = float(self.get_parameter("rate").value)
        self.deadzone = float(self.get_parameter("deadzone").value)
        chemin = str(self.get_parameter("device_path").value)

        if not chemin or chemin == "auto":
            manettes = lister_manettes()
            if not manettes:
                self.get_logger().error(
                    "aucune manette : aucun /dev/input/jsN non inertiel trouvé")
                raise SystemExit(1)
            chemin, nom = manettes[0]
            if len(manettes) > 1:
                self.get_logger().warn(
                    f"{len(manettes)} manettes vues, utilisation de la première : {chemin} ({nom})")
        else:
            nom = "chemin forcé"

        self.chemin = chemin
        self.nom = nom
        try:
            self.lecteur = LecteurJs(chemin)
        except OSError as e:
            self.get_logger().error(f"ouverture de {self.chemin} impossible : {e}")
            raise SystemExit(1)

        self._drainer_initialisation()

        self.pub = self.create_publisher(Joy, "/joy", 10)
        etat = self.lecteur.etat()
        self.get_logger().info(
            f"source /joy sur {self.chemin} ({nom}) — {len(etat.axes)} axes, "
            f"{len(etat.boutons)} boutons, {self.rate:.0f} Hz, deadzone {self.deadzone}")

    def _drainer_initialisation(self):
        """Les événements JS_EVENT_INIT annoncent axes et boutons au premier accès."""
        for _ in range(20):
            if not self.lecteur.lire(0.02):
                break
            etat = self.lecteur.etat()
            if etat.axes and etat.boutons:
                break

    def _publier(self):
        etat = self.lecteur.etat()
        msg = Joy()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "joy"
        msg.axes = [0.0 if abs(v) < self.deadzone else v for v in etat.axes]
        msg.buttons = list(etat.boutons)
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    try:
        node = JsJoySource()
    except SystemExit:
        rclpy.try_shutdown()
        return 1

    periode = 1.0 / node.rate if node.rate > 0 else 0.05
    dernier = 0.0
    try:
        while rclpy.ok():
            if not node.lecteur.lire(0.01):
                # La manette s'endort : on ferme, on attend son retour et on reprend la
                # publication sans redemarrer l'unite (REQ-OPS-057).
                node.lecteur.fermer()
                node.get_logger().warn(
                    f"manette perdue sur {node.chemin} — attente de reconnexion")
                repris = False
                while rclpy.ok() and not repris:
                    time.sleep(1.0)
                    choix = choisir_pad(lister_manettes())
                    if choix is None:
                        continue
                    chemin, nom = choix
                    try:
                        node.lecteur = LecteurJs(chemin)
                    except OSError as erreur:
                        node.get_logger().warn(f"réouverture de {chemin} impossible : {erreur}")
                        continue
                    node.chemin = chemin
                    node.nom = nom
                    node.get_logger().info(f"manette retrouvée sur {chemin} ({nom}) — reprise")
                    repris = True
                if not repris:
                    return 0
                continue
            maintenant = node.get_clock().now().nanoseconds / 1e9
            if maintenant - dernier >= periode:
                node._publier()
                dernier = maintenant
    except KeyboardInterrupt:
        pass
    finally:
        node.lecteur.fermer()
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
