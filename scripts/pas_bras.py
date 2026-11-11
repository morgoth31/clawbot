"""Un pas d'articulation, avec relecture : la commande, puis la mesure de ce qui a bougé.

Procédure imposée par le robot : jamais de trajectoire complète, des paliers de 5 à 10°, et une
relecture des angles après chaque pas. Le script refuse un saut de plus de `--max-pas` degrés et
signale un servo qui n'a pas suivi sa consigne (butée ou blocage mécanique) : c'est une information,
pas une erreur à réessayer.

    ROS_DOMAIN_ID=28 python3 scripts/pas_bras.py --servo 2 --vers 90
    ROS_DOMAIN_ID=28 python3 scripts/pas_bras.py --servo 2 --vers 70 --max-pas 7

Le script ne devine pas où est le bras : il lit `/arm/servo_angles` **avant** de construire la
consigne, parce qu'une trajectoire commande tous les axes qu'elle porte à la position supposée par
le contrôleur — un instantané périmé déplacerait des axes que personne ne visait.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "clawbot_director"))

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray

from clawbot_interfaces.srv import DirectorCommand

NOMS = ["arm_joint1", "arm_joint2", "arm_joint3", "arm_joint4", "arm_joint5"]
ZERO_SERVO_DEG = 90.0
RAD_TO_DEG = 57.29577951308232
TOLERANCE_PAS_DEG = 2.0
FRACTION_MIN = 0.6     # en dessous, on considère que le servo n'a pas suivi


def lire_angles(noeud: Node, delai_s: float = 3.0) -> list[int] | None:
    recus: list[list[int]] = []
    abonnement = noeud.create_subscription(
        Int32MultiArray, "/arm/servo_angles", lambda m: recus.append(list(m.data)), 10)
    fin = time.monotonic() + delai_s
    while time.monotonic() < fin and not recus:
        rclpy.spin_once(noeud, timeout_sec=0.1)
    noeud.destroy_subscription(abonnement)
    return recus[-1] if recus else None


def commande(noeud: Node, charge: dict, delai_s: float = 10.0) -> dict:
    """Appel ponctuel du service du directeur, dans le processus (pas de CLI)."""
    client = noeud.create_client(DirectorCommand, "/director/command")
    try:
        if not client.wait_for_service(timeout_sec=delai_s):
            return {"status": "ROS_UNAVAILABLE", "reason": "/director/command absent"}
        requete = DirectorCommand.Request()
        requete.request_json = json.dumps(charge, ensure_ascii=False)
        futur = client.call_async(requete)
        rclpy.spin_until_future_complete(noeud, futur, timeout_sec=delai_s)
        if not futur.done():
            return {"status": "ROS_TIMEOUT"}
        return json.loads(futur.result().response_json)
    finally:
        noeud.destroy_client(client)


def attendre_fin(noeud: Node, delai_s: float = 25.0) -> dict:
    fin = time.monotonic() + delai_s
    dernier: dict = {}
    while time.monotonic() < fin:
        dernier = commande(noeud, {"op": "get_task"}).get("task", {})
        if dernier.get("state") in ("DONE", "FAILED", "CANCELLED", "CANCELLED_SAFETY"):
            return dernier
        time.sleep(0.2)
    return dernier


def main() -> int:
    analyseur = argparse.ArgumentParser(description="Un pas d'articulation avec relecture")
    analyseur.add_argument("--servo", type=int, required=True, choices=[1, 2, 3, 4, 5])
    analyseur.add_argument("--vers", type=float, required=True, help="angle servo cible, en degres")
    analyseur.add_argument("--max-pas", type=float, default=10.0,
                           help="amplitude maximale d'un pas, en degres")
    analyseur.add_argument("--duree", type=float, default=1.5)
    arguments = analyseur.parse_known_args()[0]

    rclpy.init()
    noeud = Node("pas_bras")
    try:
        avant = lire_angles(noeud)
        if avant is None:
            print("ECHEC : /arm/servo_angles muet, on ne commande rien")
            return 2
        index = arguments.servo - 1
        delta = arguments.vers - avant[index]
        print(f"angles avant : {avant}")
        print(f"consigne : servo {arguments.servo} {avant[index]} -> {arguments.vers:g} "
              f"(delta {delta:+.1f} deg)")
        if abs(delta) < TOLERANCE_PAS_DEG:
            print("deja en place, rien a commander")
            return 0
        if abs(delta) > arguments.max_pas:
            print(f"REFUS : pas de {abs(delta):.1f} deg superieur a {arguments.max_pas:g} deg — "
                  "decouper en paliers")
            return 3

        cible = list(avant)
        cible[index] = int(round(arguments.vers))
        positions = [(servo - ZERO_SERVO_DEG) / RAD_TO_DEG for servo in cible[:5]]
        reponse = commande(noeud, {"op": "start_skill", "skill": "arm_move",
                                   "args": {"positions": positions, "duration_s": arguments.duree}})
        print(f"directeur : {json.dumps(reponse, ensure_ascii=False)}")
        if reponse.get("status") not in ("ACCEPTED",):
            print("ECHEC : consigne refusee, aucun mouvement envoye")
            return 4
        etat = attendre_fin(noeud)
        print(f"tache : {etat.get('state')} (motif {etat.get('reason')})")

        # La proprioception est entrelacee : un servo par tick a 10 Hz, donc ~600 ms pour un tour
        # complet. Une relecture immediate renvoie l'angle d'avant le mouvement et fait conclure a
        # tort a un blocage. On echantillonne jusqu'a voir la valeur atteindre sa cible ou 3 s.
        apres = None
        fin_lecture = time.monotonic() + 3.0
        while time.monotonic() < fin_lecture:
            candidat = lire_angles(noeud, delai_s=0.8)
            if candidat is None:
                break
            apres = candidat
            if abs(candidat[index] - arguments.vers) <= TOLERANCE_PAS_DEG:
                break
            time.sleep(0.2)
        if apres is None:
            print("ECHEC : plus de relecture apres le mouvement")
            return 5
        print(f"angles apres : {apres}")
        effectif = apres[index] - avant[index]
        attendu = arguments.vers - avant[index]
        print(f"servo {arguments.servo} : {effectif:+.1f} deg effectues sur {attendu:+.1f} attendus")
        if abs(effectif) < abs(attendu) * FRACTION_MIN:
            print("ALERTE : le servo n'a pas suivi sa consigne (butee, blocage ou couple "
                  "insuffisant) — on s'arrete la, ne pas insister")
            return 6
        return 0

    finally:
        noeud.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main() or 0)
