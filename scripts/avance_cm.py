"""Avance de N cm, en boucle fermee sur /odom, a vitesse faible.

Ne publie que sur /cmd_vel (l'arbitre reste proprietaire de la sortie). S'arrete sur la distance
atteinte, sur un defaut de securite, ou au bout du delai.

Garde-fou impose le 2026-11-11 : **la base ne bouge pas si le bras n'est pas dans sa pose de repos**
(`arm_folded: true` sur `/director/state`). Un bras en extension traverse la piece hors du costmap,
qui ne le connait que par un rayon d'encombrement. `--forcer` existe pour un cas explicite, il n'est
pas la pour contourner un refus qu'on n'a pas lu.
"""
import math
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String

import json

FORCER = "--forcer" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
DISTANCE = float(ARGS[0]) if len(ARGS) > 0 else 0.15
VITESSE = float(ARGS[1]) if len(ARGS) > 1 else 0.04
DELAI_MAX = 25.0

rclpy.init()
n = Node("avance_cm")
etat = {"odom": None, "safety": None, "directeur": None}


def _sur_directeur(m):
    try:
        etat["directeur"] = json.loads(m.data)
    except Exception:
        etat["directeur"] = None


n.create_subscription(Odometry, "/odom", lambda m: etat.update(odom=m), 10)
n.create_subscription(String, "/safety/state", lambda m: etat.update(safety=m.data), 10)
n.create_subscription(String, "/director/state", _sur_directeur, 10)
pub = n.create_publisher(Twist, "/cmd_vel", 10)


def tourner(d):
    fin = time.monotonic() + d
    while time.monotonic() < fin:
        rclpy.spin_once(n, timeout_sec=0.02)


tourner(2.0)
if etat["odom"] is None:
    print("ECHEC : /odom muet, on n'avance pas")
    raise SystemExit(2)

# Garde-fou : jamais de deplacement de base avec le bras hors de sa pose de repos.
replie = (etat["directeur"] or {}).get("arm_folded")
if replie is not True:
    angles = (etat["directeur"] or {}).get("arm_angles")
    if FORCER:
        print(f"AVERTISSEMENT : arm_folded={replie} (angles {angles}) mais --forcer est passe")
    else:
        print(f"REFUS : arm_folded={replie} (angles {angles}). Le bras doit etre en pose de repos "
              f"avant tout deplacement de la base.")
        print("        Replier : python3 scripts/moveit_plan.py 0,1.5708,-1.5708,-1.5708,0 --execute")
        print("        puis verifier : python3 scripts/etat_directeur.py")
        raise SystemExit(3)
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
