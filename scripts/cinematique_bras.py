"""Cinématique directe du bras : où regarde la caméra du poignet, et que masque-t-elle ?

Sert à choisir une pose **avant** de bouger : on calcule la direction de visée de la caméra et la
position de chaque segment pour un vecteur articulaire donné, sans rien commander.

    python3 scripts/cinematique_bras.py                  # pose courante + axes Astra
    python3 scripts/cinematique_bras.py --grille         # cherche les poses « camera vers l'avant »

Conventions : les angles sont en **degrés de servo** en entrée (`--q 76,97,90,90,90`), convertis en
radians par la correspondance du contrôleur (`servo = 90 + 57,2958 * q`), et tous les repères sont
exprimés dans `base_link`. Les valeurs de sortie sont des mesures du modèle URDF, pas du robot.
"""

from __future__ import annotations

import argparse
import math
import xml.etree.ElementTree as ET
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
URDF = RACINE / "urdf" / "clawbot_x3plus.urdf"
RAD_TO_DEG = 180.0 / math.pi
ZERO_SERVO_DEG = 90.0


def _repere(origine, rpy):
    """Matrice homogène 4x4 depuis xyz et rpy (rpy = Rz(yaw)·Ry(pitch)·Rx(roll), convention URDF)."""
    x, y, z = origine
    r, p, yaw = rpy
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr, x],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr, y],
        [-sp, cp * sr, cp * cr, z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _produit(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _rotation_axe(axe, angle):
    x, y, z = axe
    norme = math.sqrt(x * x + y * y + z * z) or 1.0
    x, y, z = x / norme, y / norme, z / norme
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    return [
        [t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0.0],
        [t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0.0],
        [t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _vecteur(valeurs):
    return [float(v) for v in valeurs.split()]


class Bras:
    def __init__(self, chemin: Path = URDF):
        racine = ET.parse(chemin).getroot()
        self.joints = {}
        for joint in racine.findall("joint"):
            origine = joint.find("origin")
            axe = joint.find("axis")
            self.joints[joint.get("name")] = {
                "type": joint.get("type"),
                "parent": joint.find("parent").get("link"),
                "child": joint.find("child").get("link"),
                "xyz": _vecteur(origine.get("xyz")) if origine is not None else [0.0, 0.0, 0.0],
                "rpy": _vecteur(origine.get("rpy")) if origine is not None else [0.0, 0.0, 0.0],
                "axis": _vecteur(axe.get("xyz")) if axe is not None else [0.0, 0.0, 1.0],
            }
        self.par_enfant = {j["child"]: (nom, j) for nom, j in self.joints.items()}

    def pose(self, lien: str, angles: dict[str, float]) -> list[list[float]]:
        """Matrice du lien dans `base_link` pour les angles articulaires donnés (radians)."""
        chaine = []
        courant = lien
        while courant in self.par_enfant:
            nom, joint = self.par_enfant[courant]
            chaine.append((nom, joint))
            courant = joint["parent"]
        matrice = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
        for nom, joint in reversed(chaine):
            matrice = _produit(matrice, _repere(joint["xyz"], joint["rpy"]))
            if joint["type"] in ("revolute", "continuous"):
                matrice = _produit(matrice, _rotation_axe(joint["axis"], angles.get(nom, 0.0)))
        return matrice

    @staticmethod
    def position(matrice):
        return (matrice[0][3], matrice[1][3], matrice[2][3])

    @staticmethod
    def axe(matrice, colonne=2):
        return (matrice[0][colonne], matrice[1][colonne], matrice[2][colonne])


def _deg(valeur_rad: float) -> float:
    return valeur_rad * RAD_TO_DEG


def _servo_vers_rad(servos: list[int]) -> dict[str, float]:
    return {f"arm_joint{i + 1}": (servo - ZERO_SERVO_DEG) / RAD_TO_DEG
            for i, servo in enumerate(servos[:5])}


def _decrire(br: Bras, angles: dict[str, float]) -> dict:
    visee = br.pose("wrist_camera_optical_frame", angles)
    avant = br.axe(visee, 2)                     # z optique = axe de visée
    position = br.position(visee)
    # tangage de l'axe optique par rapport à l'horizontale du robot : 0 = horizontal, 90 = plafond
    tangage = math.degrees(math.asin(max(-1.0, min(1.0, avant[2]))))
    lacet = math.degrees(math.atan2(avant[1], avant[0]))
    return {
        "position": position,
        "visee": avant,
        "tangage_deg": tangage,
        "lacet_deg": lacet,
        "mono": br.position(br.pose("mono_link", angles)),
        "arm_link4": br.position(br.pose("arm_link4", angles)),
        "arm_link5": br.position(br.pose("arm_link5", angles)),
    }


def main() -> int:
    analyseur = argparse.ArgumentParser(description="Cinématique directe du bras")
    analyseur.add_argument("--q", default="76,97,90,90,90",
                           help="angles servo en degres, separes par des virgules")
    analyseur.add_argument("--grille", action="store_true",
                           help="cherche les poses ou la camera regarde vers l'avant")
    arguments = analyseur.parse_known_args()[0]

    bras = Bras()

    # points fixes utiles : Astra et colonne du bras
    nul = {}
    astra = bras.position(bras.pose("camera_link", nul))
    colonne = bras.position(bras.pose("arm_link1", nul))
    print(f"Astra (camera_link)  : x={astra[0]:.3f} y={astra[1]:.3f} z={astra[2]:.3f}")
    print(f"colonne (arm_link1)  : x={colonne[0]:.3f} y={colonne[1]:.3f} z={colonne[2]:.3f}")

    if arguments.grille:
        print("\nposes ou l'axe optique est horizontal (|tangage| <= 12 deg), camera en avant :")
        meilleures = []
        for servo2 in range(-90, 60, 5):
            for servo3 in range(-90, 40, 5):
                for servo4 in (-30, -15, 0, 15, 30):
                    angles = _servo_vers_rad([90, servo2 + 90, servo3 + 90, servo4 + 90, 90])
                    infos = _decrire(bras, angles)
                    if abs(infos["tangage_deg"]) > 12:
                        continue
                    x, y, z = infos["position"]
                    if x < astra[0] + 0.02 or z < 0.08 or z > 0.30:
                        continue
                    if abs(y) > 0.12:
                        continue
                    meilleures.append((abs(infos["tangage_deg"]), servo2, servo3, servo4, infos))
        meilleures.sort(key=lambda t: (t[0], -t[4]["position"][0]))
        for _, s2, s3, s4, infos in meilleures[:10]:
            x, y, z = infos["position"]
            print(f"  servo2={s2:+4d} servo3={s3:+4d} servo4={s4:+4d} -> camera "
                  f"({x:.2f}, {y:.2f}, {z:.2f}) tangage {infos['tangage_deg']:+.1f} deg "
                  f"lacet {infos['lacet_deg']:+.1f}")
        return 0

    servos = [int(v) for v in arguments.q.split(",")]
    angles = _servo_vers_rad(servos)
    infos = _decrire(bras, angles)
    x, y, z = infos["position"]
    visee = infos["visee"]
    print(f"\npose servo {servos}")
    print(f"camera optique       : x={x:.3f} y={y:.3f} z={z:.3f}")
    print(f"axe de visee (z opt) : ({visee[0]:+.3f}, {visee[1]:+.3f}, {visee[2]:+.3f})")
    print(f"tangage {infos['tangage_deg']:+.1f} deg (0 = horizontal, +90 = plafond)  "
          f"lacet {infos['lacet_deg']:+.1f} deg")
    print(f"arm_link4            : {tuple(round(v, 3) for v in infos['arm_link4'])}")
    print(f"arm_link5 (pince)    : {tuple(round(v, 3) for v in infos['arm_link5'])}")
    hauteur_astra = astra[2]
    if z > hauteur_astra:
        print(f"\nla camera est au-dessus de l'Astra ({z:.2f} > {hauteur_astra:.2f})")
    else:
        print(f"\nla camera est sous l'Astra ({z:.2f} < {hauteur_astra:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
