"""brasd — client persistant pour le bras, le directeur et les caméras.

**Le problème qu'il resout.** Chaque observation du robot en lancant un nouveau processus coute
1 a 2,4 s : demarrage de Python, `rclpy.init`, creation du noeud, decouverte DDS du service ou du
topic. Mesure du 2026-11-11 : `ros2 topic echo --once` 2,41 s, un appel `/director/command`
2,29 s, `etat_directeur.py` 1,04 s — pour lire un tableau de six entiers. Une seance de diagnostic
qui pose cinquante questions paye donc une minute et demie de mise en route, et c'est ce qui fait
croire que « le robot est lent » : ses boucles de controle, elles, tournent a 20 Hz.

`brasd` demarre **un seul** noeud, garde les abonnements et le client de service ouverts, et repond
sur une socket Unix. Chaque requete coute ensuite quelques millisecondes.

    python3 scripts/brasd.py &                 # ou via systemd --user
    python3 scripts/bras.py etat
    python3 scripts/bras.py pas --servo 1 --vers 96
    python3 scripts/bras.py mesure               # barycentre de la pince, image frontale
    python3 scripts/bras.py image --camera poignet --sortie /tmp/p.png

Les attentes sont **conditionnelles** : on attend que la valeur change ou qu'un delai expire, on ne
dort jamais un temps fixe.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import socket
import socketserver
import threading
import time
from pathlib import Path

import numpy as np
import rclpy
from PIL import Image as PILImage
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import Int32MultiArray, String

import sys

sys.path.insert(0, "/home/jetson/clawbot")
from clawbot_interfaces.srv import DirectorCommand  # noqa: E402

SOCKET = os.environ.get("BRASD_SOCKET", "/tmp/brasd.sock")
ZERO = 90.0
RAD = 57.29577951
SEUIL_SOMBRE = 70


class Bras(Node):
    def __init__(self):
        super().__init__("brasd")
        self.angles = None
        self.t_angles = 0.0
        self.safety = None
        self.directeur = None
        self.front = None
        self.poignet = None
        self.create_subscription(Int32MultiArray, "/arm/servo_angles", self._sur_angles, 10)
        self.create_subscription(String, "/safety/state", lambda m: setattr(self, "safety", m.data), 10)
        self.create_subscription(String, "/director/state", self._sur_directeur, 10)
        self.create_subscription(Image, "/camera/color/image_raw", self._sur_front, 10)
        self.create_subscription(CompressedImage, "/wrist_camera/image_raw/compressed",
                                 self._sur_poignet, 10)
        self.cli = self.create_client(DirectorCommand, "/director/command")

    def _sur_angles(self, m):
        self.angles = list(m.data)
        self.t_angles = time.monotonic()

    def _sur_directeur(self, m):
        try:
            self.directeur = json.loads(m.data)
        except Exception:
            self.directeur = None

    def _sur_front(self, m):
        self.front = (m.height, m.width, bytes(m.data), m.encoding)

    def _sur_poignet(self, m):
        self.poignet = bytes(m.data)

    # ── attentes conditionnelles ────────────────────────────────────────────────
    def attendre(self, predicat, delai=5.0, periode=0.01):
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            if predicat():
                return True
            time.sleep(periode)
        return predicat()

    def angles_frais(self, max_age=1.0):
        return self.angles is not None and (time.monotonic() - self.t_angles) < max_age

    # ── commandes ───────────────────────────────────────────────────────────────
    def commande(self, charge, delai=5.0):
        if not self.cli.wait_for_service(timeout_sec=delai):
            return {"status": "ROS_UNAVAILABLE"}
        req = DirectorCommand.Request()
        req.request_json = json.dumps(charge, ensure_ascii=False)
        fut = self.cli.call_async(req)
        fin = time.monotonic() + delai
        while time.monotonic() < fin and not fut.done():
            time.sleep(0.005)
        return json.loads(fut.result().response_json) if fut.done() else {"status": "ROS_TIMEOUT"}

    def tache(self, delai=20.0):
        fin = time.monotonic() + delai
        etat = {}
        while time.monotonic() < fin:
            etat = self.commande({"op": "get_task"}).get("task", {}) or {}
            if etat.get("state") in ("DONE", "FAILED", "CANCELLED", "CANCELLED_SAFETY"):
                return etat
            time.sleep(0.05)
        return etat

    def pas(self, servo, vers, duree=1.2, max_pas=10.0):
        if not self.angles_frais():
            self.attendre(self.angles_frais, 3.0)
        avant = list(self.angles)
        delta = vers - avant[servo - 1]
        if abs(delta) > max_pas + 1:
            return {"erreur": f"pas de {abs(delta):.0f} deg > {max_pas:g}", "angles": avant}
        positions = [(s - ZERO) / RAD for s in avant[:5]]
        positions[servo - 1] = (vers - ZERO) / RAD
        rep = self.commande({"op": "start_skill", "skill": "arm_move",
                             "args": {"positions": positions, "duration_s": duree}})
        if rep.get("status") != "ACCEPTED":
            return {"erreur": f"refus {rep.get('status')}", "angles": avant}
        etat = self.tache()
        cible = int(round(vers))
        self.attendre(lambda: self.angles and abs(self.angles[servo - 1] - cible) <= 1, 2.0)
        return {"tache": etat.get("state"), "avant": avant, "apres": list(self.angles or [])}

    # ── mesures ─────────────────────────────────────────────────────────────────
    def image_front(self):
        self.front = None
        if not self.attendre(lambda: self.front is not None, 3.0):
            return None
        h, w, data, enc = self.front
        canaux = {"rgb8": 3, "bgr8": 3, "yuv422_yuy2": 2}.get(enc)
        if canaux == 2:
            import cv2
            brute = np.frombuffer(data, np.uint8).reshape(h, w, 2)
            return cv2.cvtColor(brute, cv2.COLOR_YUV2RGB_YUYV)
        tab = np.frombuffer(data, np.uint8).reshape(h, w, canaux)
        return tab[:, :, ::-1] if enc == "bgr8" else tab

    def mesure_pince(self):
        img = self.image_front()
        if img is None:
            return {"erreur": "image frontale absente"}
        gris = img.mean(axis=2)
        masque = gris < SEUIL_SOMBRE
        masque[: int(gris.shape[0] * 0.10)] = False
        if masque.sum() < 500:
            return {"erreur": "masque trop petit", "aire": int(masque.sum())}
        ys, xs = np.nonzero(masque)
        return {"x": round(float(xs.mean()), 1), "y": round(float(ys.mean()), 1),
                "aire": int(masque.sum())}

    def photo(self, camera, chemin):
        if camera == "poignet":
            self.poignet = None
            if not self.attendre(lambda: self.poignet is not None, 4.0):
                return {"erreur": "flux poignet muet"}
            PILImage.open(io.BytesIO(self.poignet)).save(chemin)
        else:
            img = self.image_front()
            if img is None:
                return {"erreur": "flux frontal muet"}
            PILImage.fromarray(img).save(chemin)
        return {"chemin": str(chemin)}


def servir(bras: Bras):
    class Gestionnaire(socketserver.StreamRequestHandler):
        def handle(self):
            ligne = self.rfile.readline().decode("utf-8").strip()
            if not ligne:
                return
            t0 = time.monotonic()
            try:
                demande = json.loads(ligne)
                action = demande.get("cmd")
                if action == "etat":
                    reponse = {
                        "angles": bras.angles,
                        "age_s": round(time.monotonic() - bras.t_angles, 3) if bras.angles else None,
                        "safety": bras.safety,
                        "arm_folded": (bras.directeur or {}).get("arm_folded"),
                        "directeur": (bras.directeur or {}).get("state"),
                    }
                elif action == "pas":
                    reponse = bras.pas(int(demande["servo"]), float(demande["vers"]),
                                       float(demande.get("duree", 1.2)))
                elif action == "pince":
                    rep = bras.commande({"op": "start_skill", "skill": "grip_set",
                                         "args": {"position": float(demande["position"]),
                                                  "duration_s": float(demande.get("duree", 1.5))}})
                    bras.tache(10.0)
                    reponse = {"reponse": rep, "angles": bras.angles}
                elif action == "mesure":
                    reponse = bras.mesure_pince()
                elif action == "image":
                    reponse = bras.photo(demande.get("camera", "front"), demande["sortie"])
                elif action == "ping":
                    reponse = {"pong": True}
                else:
                    reponse = {"erreur": f"commande inconnue {action!r}"}
            except Exception as exc:  # noqa: BLE001 - le serveur ne doit jamais mourir
                reponse = {"erreur": f"{type(exc).__name__}: {exc}"}
            reponse["ms"] = round((time.monotonic() - t0) * 1000, 1)
            self.wfile.write((json.dumps(reponse) + "\n").encode("utf-8"))

    class Serveur(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True

    if os.path.exists(SOCKET):
        os.unlink(SOCKET)
    serveur = Serveur(SOCKET, Gestionnaire)
    os.chmod(SOCKET, 0o666)
    print(f"brasd pret sur {SOCKET}", flush=True)
    serveur.serve_forever()


def main() -> int:
    argparse.ArgumentParser(description="Client persistant du bras").parse_known_args()
    rclpy.init()
    bras = Bras()
    threading.Thread(target=rclpy.spin, args=(bras,), daemon=True).start()
    # on ne repond que lorsque les premiers messages sont arrives : la premiere requete ne paie pas
    # la decouverte, elle trouve un noeud deja abonne.
    bras.attendre(bras.angles_frais, 10.0)
    try:
        servir(bras)
    except KeyboardInterrupt:
        pass
    finally:
        bras.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
