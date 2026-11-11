"""Avance de N cm, en boucle fermee sur /odom, a vitesse faible.

Ne publie que sur /cmd_vel (l'arbitre reste proprietaire de la sortie). S'arrete sur la distance
atteinte, sur un defaut de securite, ou au bout du delai.
"""
import math
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String

DISTANCE = float(sys.argv[1]) if len(sys.argv) > 1 else 0.15
VITESSE = float(sys.argv[2]) if len(sys.argv) > 2 else 0.04
DELAI_MAX = 25.0

rclpy.init()
n = Node("avance_cm")
etat = {"odom": None, "safety": None}
n.create_subscription(Odometry, "/odom", lambda m: etat.update(odom=m), 10)
n.create_subscription(String, "/safety/state", lambda m: etat.update(safety=m.data), 10)
pub = n.create_publisher(Twist, "/cmd_vel", 10)


def tourner(d):
    fin = time.monotonic() + d
    while time.monotonic() < fin:
        rclpy.spin_once(n, timeout_sec=0.02)


tourner(1.5)
if etat["odom"] is None:
    print("ECHEC : /odom muet, on n'avance pas")
    raise SystemExit(2)
depart = etat["odom"].pose.pose.position
print(f"depart : x={depart.x:+.3f} y={depart.y:+.3f}   consigne {VITESSE} m/s sur {DISTANCE*100:.0f} cm")

t0 = time.monotonic()
atteint = False
while time.monotonic() - t0 < DELAI_MAX:
    p = etat["odom"].pose.pose.position
    parcouru = math.hypot(p.x - depart.x, p.y - depart.y)
    if parcouru >= DISTANCE:
        atteint = True
        break
    if etat["safety"] not in (None, "OK"):
        print(f"ARRET : /safety/state = {etat['safety']}")
        break
    vitesse = Twist()
    vitesse.linear.x = VITESSE
    pub.publish(vitesse)
    tourner(0.05)

for _ in range(20):                     # consignes nulles franches
    pub.publish(Twist())
    tourner(0.05)

p = etat["odom"].pose.pose.position
parcouru = math.hypot(p.x - depart.x, p.y - depart.y)
print(f"arrivee : x={p.x:+.3f} y={p.y:+.3f}   parcouru {parcouru*100:.1f} cm en "
      f"{time.monotonic()-t0:.1f} s ({'cible atteinte' if atteint else 'delai epuise'})")
n.destroy_node()
rclpy.try_shutdown()
