"""Envoie une commande a `brasd` et affiche la reponse. Cout : quelques millisecondes.

    python3 scripts/bras.py etat
    python3 scripts/bras.py pas --servo 1 --vers 96
    python3 scripts/bras.py pince --position -1.54
    python3 scripts/bras.py mesure
    python3 scripts/bras.py image --camera poignet --sortie /tmp/p.png
    python3 scripts/bras.py ping
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys

SOCKET = os.environ.get("BRASD_SOCKET", "/tmp/brasd.sock")


def main() -> int:
    ap = argparse.ArgumentParser(description="Client de brasd")
    ap.add_argument("cmd", choices=["etat", "pas", "pince", "mesure", "image", "ping"])
    ap.add_argument("--servo", type=int)
    ap.add_argument("--vers", type=float)
    ap.add_argument("--position", type=float)
    ap.add_argument("--duree", type=float, default=None)
    ap.add_argument("--camera", default="front")
    ap.add_argument("--sortie", default="/tmp/brasd_image.png")
    a, _ = ap.parse_known_args()

    demande = {"cmd": a.cmd}
    if a.cmd == "pas":
        if a.servo is None or a.vers is None:
            print("pas : --servo et --vers sont requis")
            return 2
        demande.update(servo=a.servo, vers=a.vers)
    if a.cmd == "pince":
        if a.position is None:
            print("pince : --position est requis (radians, -1.54 = ouvert, 0 = ferme)")
            return 2
        demande["position"] = a.position
    if a.duree is not None:
        demande["duree"] = a.duree
    if a.cmd == "image":
        demande.update(camera=a.camera, sortie=a.sortie)

    if not os.path.exists(SOCKET):
        print(f"brasd n'ecoute pas sur {SOCKET} — le lancer : python3 scripts/brasd.py &")
        return 3
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(60.0)
        s.connect(SOCKET)
        s.sendall((json.dumps(demande) + "\n").encode("utf-8"))
        tampon = b""
        while not tampon.endswith(b"\n"):
            morceau = s.recv(65536)
            if not morceau:
                break
            tampon += morceau
    if not tampon.strip():
        print("reponse vide — brasd a-t-il plante ?")
        return 4
    print(json.dumps(json.loads(tampon.decode("utf-8")), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
