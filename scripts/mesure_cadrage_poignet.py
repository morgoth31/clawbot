"""Cadrage et netteté de la caméra du poignet, mesurés pose par pose.

La caméra du poignet est solidaire du bras : « l'image est sans détail » ne veut rien dire tant qu'on
ne dit pas **dans quelle pose**. Ce script fait défiler un axe par paliers de 10° (jamais une
trajectoire complète), s'arrête à chaque cible pour capturer une image du poignet et rend, par pose :

  - la luminance moyenne et son écart-type ;
  - la **netteté**, variance du Laplacien (7 sur une surface lisse, des centaines sur une scène
    texturée et nette) ;
  - la fraction de pixels saturés (255) — une image blanche n'est pas floue, elle est surexposée ;
  - une capture PNG pour juger le cadrage.

    ROS_DOMAIN_ID=28 source_ros
    python3 scripts/mesure_cadrage_poignet.py --axe 2 --vers 180,160,140
    python3 scripts/mesure_cadrage_poignet.py --axe 1 --vers 90,110,120 --axe-precedent

Le bras revient à sa pose de départ à la fin (`--garder` pour l'éviter).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
import rclpy
from PIL import Image as PILImage
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Int32MultiArray, String

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from clawbot_interfaces.srv import DirectorCommand  # noqa: E402

ZERO_SERVO_DEG = 90.0
RAD_TO_DEG = 57.29577951308232
PAS_MAX = 10.0


def nettete(gris: np.ndarray) -> float:
    """Variance du Laplacien, sans OpenCV (noyau 4-voisins)."""
    g = gris.astype(np.float64)
    laplacien = (-4.0 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    return float(laplacien.var())


class Sonde(Node):
    def __init__(self):
        super().__init__("mesure_cadrage_poignet")
        self.angles = None
        self.safety = None
        self.images = []
        self.create_subscription(Int32MultiArray, "/arm/servo_angles",
                                 lambda m: setattr(self, "angles", list(m.data)), 10)
        self.create_subscription(String, "/safety/state",
                                 lambda m: setattr(self, "safety", m.data), 10)
        self.create_subscription(CompressedImage, "/wrist_camera/image_raw/compressed",
                                 lambda m: self.images.append(bytes(m.data)), 10)
        self.cli = self.create_client(DirectorCommand, "/director/command")

    def tourner(self, duree):
        fin = time.monotonic() + duree
        while time.monotonic() < fin:
            rclpy.spin_once(self, timeout_sec=0.05)

    def relire(self, delai=4.0):
        fin = time.monotonic() + delai
        while time.monotonic() < fin and self.angles is None:
            rclpy.spin_once(self, timeout_sec=0.05)
        return self.angles

    def commande(self, charge, delai=10.0):
        if not self.cli.wait_for_service(timeout_sec=delai):
            return {"status": "ROS_UNAVAILABLE"}
        req = DirectorCommand.Request()
        req.request_json = json.dumps(charge, ensure_ascii=False)
        fut = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=delai)
        return json.loads(fut.result().response_json) if fut.done() else {"status": "ROS_TIMEOUT"}

    def attendre(self, delai=25.0):
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            etat = self.commande({"op": "get_task"}).get("task", {}) or {}
            if etat.get("state") in ("DONE", "FAILED", "CANCELLED", "CANCELLED_SAFETY"):
                return etat
            time.sleep(0.2)
        return {}

    def deplacer(self, axe, cible):
        """Amène un servo à sa cible par paliers de 10°, en relisant entre chaque."""
        courant = self.relire()[axe - 1]
        while abs(cible - courant) > 1:
            if self.safety not in (None, "OK"):
                raise SystemExit(f"ARRET : /safety/state = {self.safety}")
            suivant = courant + int(np.sign(cible - courant) * min(abs(cible - courant), PAS_MAX))
            positions = [(s - ZERO_SERVO_DEG) / RAD_TO_DEG for s in self.angles[:5]]
            positions[axe - 1] = (suivant - ZERO_SERVO_DEG) / RAD_TO_DEG
            rep = self.commande({"op": "start_skill", "skill": "arm_move",
                                 "args": {"positions": positions, "duration_s": 1.2}})
            if rep.get("status") != "ACCEPTED":
                raise SystemExit(f"REFUS a {suivant} : {rep}")
            etat = self.attendre()
            if etat.get("state") != "DONE":
                raise SystemExit(f"tache {etat.get('state')} sur le palier {suivant}")
            self.tourner(0.8)
            courant = self.relire()[axe - 1]
        return courant

    def capturer(self, chemin: Path):
        self.images.clear()
        fin = time.monotonic() + 8.0
        while time.monotonic() < fin and not self.images:
            rclpy.spin_once(self, timeout_sec=0.05)
        if not self.images:
            return None
        img = PILImage.open(io.BytesIO(self.images[-1]))
        gris = np.asarray(img.convert("L"))
        if chemin is not None:
            img.save(chemin)
        return {
            "moyenne": float(gris.mean()),
            "ecart_type": float(gris.std()),
            "nettete": nettete(gris),
            "satures": float((gris == 255).mean() * 100.0),
            "chemin": str(chemin) if chemin else None,
        }


def main() -> int:
    analyseur = argparse.ArgumentParser(description="Cadrage et netteté du poignet par pose")
    analyseur.add_argument("--axe", type=int, required=True, choices=[1, 2, 3, 4, 5])
    analyseur.add_argument("--vers", required=True, help="cibles séparées par des virgules")
    analyseur.add_argument("--sortie", default="/home/jetson/.hermes/cache/scratch/poignet")
    analyseur.add_argument("--garder", action="store_true", help="ne pas revenir à la pose de départ")
    arguments = analyseur.parse_known_args()[0]

    cibles = [int(v) for v in arguments.vers.split(",")]
    dossier = Path(arguments.sortie)
    dossier.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    sonde = Sonde()
    try:
        depart = sonde.relire()
        if depart is None:
            print("ECHEC : /arm/servo_angles muet")
            return 2
        print(f"pose de depart : {depart}")
        print(f"{'cible':>6} {'relu':>5} {'moyenne':>8} {'ecart-t':>8} {'nettete':>9} "
              f"{'satures':>8}  capture")
        for cible in cibles:
            relu = sonde.deplacer(arguments.axe, cible)
            stats = sonde.capturer(dossier / f"axe{arguments.axe}_{relu:03d}.png")
            if stats is None:
                print(f"{cible:>6} {relu:>5}   image non recue")
                continue
            print(f"{cible:>6} {relu:>5} {stats['moyenne']:>8.1f} {stats['ecart_type']:>8.1f} "
                  f"{stats['nettete']:>9.1f} {stats['satures']:>7.0f}%  {stats['chemin']}")
        if not arguments.garder:
            sonde.deplacer(arguments.axe, depart[arguments.axe - 1])
            print(f"retour a la pose de depart : {sonde.relire()}")
        return 0
    finally:
        sonde.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
