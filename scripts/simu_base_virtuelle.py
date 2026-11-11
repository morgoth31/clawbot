"""Base mobile virtuelle pour éprouver la navigation sans déplacer le robot.

Ce nœud tient le rôle du couple driver + lidar : il encaisse `/cmd_vel`, intègre la pose, publie
`/odom` et la TF `odom -> base_link`, et fabrique un `/scan` par lancer de rayons sur le fichier de
carte réel. Tout ce qui tourne au-dessus — Nav2, AMCL, le directeur, `navigate_to` — ne sait pas
que la base est simulée : c'est ce qui rend la mesure défendable.

Deux détails qui comptent :

  - les rayons s'arrêtent sur toute cellule **non libre** de la carte, espace inconnu compris :
    un scan qui traverserait l'inconnu ferait croire à AMCL que le robot voit à travers les murs ;
  - le domaine 99 est imposé au démarrage : cette base écrit une TF et une odométrie qui
    contrediraient le vrai robot si elle tournait en domaine 28.

Lancer seul (pour vérifier les cadences) :
  ROS_DOMAIN_ID=99 python3 scripts/simu_base_virtuelle.py --x 1.5 --y -0.3
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from collections import deque

if os.environ.get("ROS_DOMAIN_ID") not in (None, "", "99"):
    raise SystemExit(
        f"ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']} refuse : la base virtuelle ne tourne qu'en 99")

import rclpy
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster

CARTE_PAR_DEFAUT = "/home/jetson/clawbot/maps/test_cartographie_apres_deplacement.yaml"
DEPORT_LASER_X = 0.105          # base_link -> laser_link, mesuré dans l'URDF
ANGLE_MIN, ANGLE_MAX = -math.pi, math.pi
PORTEE_MIN, PORTEE_MAX = 0.12, 8.0


def _lire_pgm(chemin: str):
    donnees = open(chemin, "rb").read()
    jetons, i = [], 0
    while len(jetons) < 4:
        while donnees[i:i + 1].isspace():
            i += 1
        if donnees[i:i + 1] == b"#":
            while donnees[i:i + 1] not in (b"\n", b""):
                i += 1
            continue
        j = i
        while not donnees[j:j + 1].isspace():
            j += 1
        jetons.append(donnees[i:j])
        i = j
    largeur, hauteur = int(jetons[1]), int(jetons[2])
    return largeur, hauteur, donnees[i + 1:i + 1 + largeur * hauteur]


class Grille:
    """Carte d'occupation + champ de distance, pour un lancer de rayons par sphères tangentes."""

    def __init__(self, yaml_carte: str):
        import yaml
        meta = yaml.safe_load(open(yaml_carte, encoding="utf-8").read())
        self.resolution = float(meta["resolution"])
        self.origine = [float(v) for v in meta["origin"]]
        chemin = os.path.join(os.path.dirname(yaml_carte), meta["image"])
        self.largeur, self.hauteur, pixels = _lire_pgm(chemin)
        # obstacle = tout ce qui n'est pas libre : l'inconnu arrête un rayon, il ne le laisse
        # pas passer (sinon AMCL croit voir à travers les murs)
        libre = [[(255 - pixels[l * self.largeur + c]) / 255.0 <= 0.25
                  for c in range(self.largeur)] for l in range(self.hauteur)]
        self.distance = self._champ_de_distance(libre)

    def _champ_de_distance(self, libre):
        infini = 10 ** 9
        distance = [[infini] * self.largeur for _ in range(self.hauteur)]
        file = deque()
        for l in range(self.hauteur):
            for c in range(self.largeur):
                if not libre[l][c]:
                    distance[l][c] = 0
                    file.append((c, l))
        while file:
            c, l = file.popleft()
            for dc, dl in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nc, nl = c + dc, l + dl
                if 0 <= nc < self.largeur and 0 <= nl < self.hauteur and distance[nl][nc] == infini:
                    distance[nl][nc] = distance[l][c] + 1
                    file.append((nc, nl))
        return [[d * self.resolution for d in ligne] for ligne in distance]

    def distance_en(self, x: float, y: float) -> float:
        c = int((x - self.origine[0]) / self.resolution)
        l = self.hauteur - 1 - int((y - self.origine[1]) / self.resolution)
        if not (0 <= c < self.largeur and 0 <= l < self.hauteur):
            return 0.0
        return self.distance[l][c]

    def portee(self, x: float, y: float, angle: float, portee_max: float) -> float:
        """Distance au premier obstacle par pas tangents au champ de distance."""
        dx, dy = math.cos(angle), math.sin(angle)
        t = 0.0
        while t < portee_max:
            d = self.distance_en(x + t * dx, y + t * dy)
            if d <= self.resolution * 0.5:
                return max(PORTEE_MIN, t)
            t += max(self.resolution, min(d * 0.8, 0.50))
        return float("inf")


class BaseVirtuelle(Node):
    def __init__(self, yaml_carte: str, x: float, y: float, yaw: float,
                 faisceaux: int = 240, cadence_scan: float = 8.0):
        super().__init__("base_virtuelle")
        self.grille = Grille(yaml_carte)
        self.x, self.y, self.yaw = float(x), float(y), float(yaw)
        self.vx = self.wz = 0.0
        self.faisceaux = faisceaux
        self._aleatoire = random.Random(20261111)

        self.pub_odom = self.create_publisher(Odometry, "/odom", 20)
        self.pub_scan = self.create_publisher(LaserScan, "/scan", 10)
        self.tf = TransformBroadcaster(self)
        self.tf_static = StaticTransformBroadcaster(self)
        self.create_subscription(Twist, "/cmd_vel", self.on_cmd, 10)

        self._publier_tf_statique()
        self.create_timer(0.05, self.tick_odom)          # 20 Hz
        self.create_timer(1.0 / cadence_scan, self.tick_scan)
        self.get_logger().info(
            f"base virtuelle en ({self.x:.2f}, {self.y:.2f}, {self.yaw:.2f}) "
            f"sur {os.path.basename(yaml_carte)}")

    # ── entrées ─────────────────────────────────────────────────────────
    def on_cmd(self, msg: Twist):
        self.vx = float(msg.linear.x)
        self.wz = float(msg.angular.z)

    # ── sorties ────────────────────────────────────────────────────────
    def tick_odom(self):
        dt = 0.05
        self.x += self.vx * math.cos(self.yaw) * dt
        self.y += self.vx * math.sin(self.yaw) * dt
        self.yaw += self.wz * dt
        self.yaw = math.atan2(math.sin(self.yaw), math.cos(self.yaw))

        horodatage = self.get_clock().now().to_msg()
        odom = Odometry()
        odom.header.stamp = horodatage
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = math.sin(self.yaw / 2.0)
        odom.pose.pose.orientation.w = math.cos(self.yaw / 2.0)
        odom.pose.covariance[0] = odom.pose.covariance[7] = 1e-4
        odom.pose.covariance[35] = 1e-4
        odom.twist.twist.linear.x = self.vx
        odom.twist.twist.angular.z = self.wz
        self.pub_odom.publish(odom)

        transformee = TransformStamped()
        transformee.header.stamp = horodatage
        transformee.header.frame_id = "odom"
        transformee.child_frame_id = "base_link"
        transformee.transform.translation.x = self.x
        transformee.transform.translation.y = self.y
        transformee.transform.rotation.z = math.sin(self.yaw / 2.0)
        transformee.transform.rotation.w = math.cos(self.yaw / 2.0)
        self.tf.sendTransform(transformee)

    def tick_scan(self):
        origine_x = self.x + DEPORT_LASER_X * math.cos(self.yaw)
        origine_y = self.y + DEPORT_LASER_X * math.sin(self.yaw)
        pas = (ANGLE_MAX - ANGLE_MIN) / (self.faisceaux - 1)
        portees = []
        for i in range(self.faisceaux):
            angle_monde = self.yaw + ANGLE_MIN + i * pas
            brut = self.grille.portee(origine_x, origine_y, angle_monde, PORTEE_MAX)
            if brut != float("inf"):
                brut += self._aleatoire.gauss(0.0, 0.005)
            portees.append(brut)

        scan = LaserScan()
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.header.frame_id = "laser_link"
        scan.angle_min = ANGLE_MIN
        scan.angle_max = ANGLE_MAX
        scan.angle_increment = pas
        scan.time_increment = 0.0
        scan.scan_time = 1.0 / 8.0
        scan.range_min = PORTEE_MIN
        scan.range_max = PORTEE_MAX
        scan.ranges = portees
        self.pub_scan.publish(scan)

    def _publier_tf_statique(self):
        # En domaine 28 cette transformation vient de robot_state_publisher ; ici il n'y a pas
        # d'URDF, et sans elle AMCL ne peut pas rattacher /scan à base_link.
        statique = TransformStamped()
        statique.header.stamp = self.get_clock().now().to_msg()
        statique.header.frame_id = "base_link"
        statique.child_frame_id = "laser_link"
        statique.transform.translation.x = DEPORT_LASER_X
        statique.transform.rotation.w = 1.0
        self.tf_static.sendTransform(statique)


def main(argv=None):
    """Point d'entrée ; les arguments sont lus avant rclpy pour ne pas finir dans --ros-args."""
    analyseur = argparse.ArgumentParser(description="Base mobile virtuelle (domaine 99)")
    analyseur.add_argument("--carte", default=CARTE_PAR_DEFAUT,
                           help="chemin du .yaml de carte, sans extension")
    analyseur.add_argument("--x", type=float, default=1.50)
    analyseur.add_argument("--y", type=float, default=-0.30)
    analyseur.add_argument("--yaw", type=float, default=0.0)
    analyseur.add_argument("--faisceaux", type=int, default=240)
    arguments = analyseur.parse_known_args(argv)[0]

    rclpy.init(args=None)
    noeud = BaseVirtuelle(arguments.carte, arguments.x, arguments.y, arguments.yaw,
                          arguments.faisceaux)
    try:
        rclpy.spin(noeud)
    except KeyboardInterrupt:
        pass
    finally:
        noeud.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

