"""Preuve de bout en bout de la brique 5, en simulation, sans déplacer le robot.

Ce que ce script mesure, et qui est le critère de sortie du lot :

  « 3 waypoints nommés atteints à ±20 cm, get_task montre les étapes »

Il monte, en **domaine 99** uniquement :
  - la base virtuelle (`scripts/simu_base_virtuelle.py`), qui publie /odom, /tf et un /scan
    fabriqué par lancer de rayons sur le vrai fichier de carte ;
  - Nav2, avec **exactement** les paramètres du robot (`config/nav2_clawbot.yaml`) et la carte du
    catalogue — mêmes cadres, mêmes vitesses, même tolérance ;
  - le directeur réel, alimenté par un `/safety/state = OK` à 20 Hz.

Puis il déclare une séquence de trois `navigate_to` nommés au directeur, laisse Nav2 conduire, et
compare la pose de la base virtuelle à la pose du catalogue au moment de chaque arrivée.

Ce que cette preuve **ne** couvre pas, et qui reste à faire sur le robot : la physique de la base
(adhérence, temps mort du MCU de 0,85 s, glissement des roues Mecanum) et la justesse d'AMCL sur un
scan réel. Le script le dit à la fin plutôt que de le laisser croire.

    cd /home/jetson/clawbot
    ROS_DOMAIN_ID=99 unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
    source /opt/ros/humble/setup.bash && source install/setup.bash
    python3 scripts/preuve_navigation_99.py
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

if os.environ.get("ROS_DOMAIN_ID") not in (None, "", "99"):
    raise SystemExit(
        f"ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']} refuse : cette preuve conduit une base "
        "virtuelle et ne doit jamais tourner dans le domaine du robot")

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "scripts"))
sys.path.insert(0, str(RACINE / "clawbot_director"))

import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor, SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from clawbot_director.director_node import DirectorNode
from clawbot_director import waypoints as catalogue_waypoints
from clawbot_interfaces.srv import DirectorCommand
from nav2_msgs.action import NavigateToPose
from simu_base_virtuelle import BaseVirtuelle

SEQUENCE = ("ouest", "centre", "est")
TOLERANCE_M = 0.20
DELAI_DEMARRAGE_NAV2_S = 90.0
DELAI_SEQUENCE_S = 240.0
JOURNAL_NAV2 = Path("/tmp/preuve_navigation_99_nav2.log")


class Preuve:
    def __init__(self):
        self.catalogue = catalogue_waypoints.charger()
        self.base = BaseVirtuelle(str(RACINE / "maps" / f"{self.catalogue.carte}.yaml"),
                                  x=self.catalogue.resoudre(SEQUENCE[0]).x,
                                  y=self.catalogue.resoudre(SEQUENCE[0]).y,
                                  yaw=self.catalogue.resoudre(SEQUENCE[0]).yaw)
        self.directeur = DirectorNode()
        self.sonde = Node("sonde_preuve")
        self.pub_safety = self.sonde.create_publisher(String, "/safety/state", 10)
        self.client_directeur = self.sonde.create_client(DirectorCommand, "/director/command")
        self.client_nav2 = ActionClient(self.sonde, NavigateToPose, "/navigate_to_pose")

        self._executeur = MultiThreadedExecutor(num_threads=6)
        self._executeur.add_node(self.base)
        self._executeur.add_node(self.directeur)
        self._executeur.add_node(self.sonde)
        self._arrete = threading.Event()
        threading.Thread(target=self._executeur.spin, daemon=True).start()
        threading.Thread(target=self._alimenter_safety, daemon=True).start()

    def _alimenter_safety(self):
        while not self._arrete.is_set():
            self.pub_safety.publish(String(data="OK"))
            time.sleep(0.05)

    # ── appels ────────────────────────────────────────────────────────────
    def commande(self, charge: dict, timeout: float = 15.0) -> dict:
        if not self.client_directeur.wait_for_service(timeout_sec=timeout):
            raise RuntimeError("service /director/command muet")
        requete = DirectorCommand.Request()
        requete.request_json = json.dumps(charge)
        futur = self.client_directeur.call_async(requete)
        fin = time.monotonic() + timeout
        while not futur.done() and time.monotonic() < fin:
            time.sleep(0.01)
        if not futur.done():
            raise RuntimeError("le directeur n'a pas repondu")
        return json.loads(futur.result().response_json)

    def etat(self) -> dict:
        return self.commande({"op": "get_task"})["task"]

    def pose(self):
        return (self.base.x, self.base.y, self.base.yaw)

    # ── déroulement ───────────────────────────────────────────────────────
    def attendre_nav2(self) -> float:
        """Attend que Nav2 soit *actif*, pas seulement que son serveur d'action existe.

        Un nœud Nav2 crée son serveur d'action avant d'être activé par le gestionnaire de cycle
        de vie ; un goal envoyé dans cet intervalle est refusé, et le directeur — à raison —
        marque l'étape en échec. On interroge donc les deux gestionnaires.
        """
        from std_srvs.srv import Trigger
        debut = time.monotonic()
        gestionnaires = [
            self.sonde.create_client(Trigger, "/lifecycle_manager_localization/is_active"),
            self.sonde.create_client(Trigger, "/lifecycle_manager_navigation/is_active"),
        ]
        while time.monotonic() - debut < DELAI_DEMARRAGE_NAV2_S:
            if all(client.service_is_ready() for client in gestionnaires) \
                    and self.client_nav2.server_is_ready():
                actifs = 0
                for client in gestionnaires:
                    futur = client.call_async(Trigger.Request())
                    fin = time.monotonic() + 2.0
                    while not futur.done() and time.monotonic() < fin:
                        time.sleep(0.01)
                    if futur.done() and futur.result() and futur.result().success:
                        actifs += 1
                if actifs == len(gestionnaires):
                    return time.monotonic() - debut
            time.sleep(0.5)
        raise RuntimeError(
            f"Nav2 inactif apres {DELAI_DEMARRAGE_NAV2_S:g} s — voir {JOURNAL_NAV2}")

    def jouer(self) -> dict:
        etapes = [{"skill": "navigate_to", "args": {"destination": nom}} for nom in SEQUENCE]
        depart = self.commande({"op": "start_sequence", "steps": etapes})
        if depart.get("status") != "ACCEPTED":
            raise RuntimeError(f"sequence refusee : {depart}")

        arrivees = []
        etape_vue = 0
        etat = self.etat()
        debut = time.monotonic()
        while time.monotonic() - debut < DELAI_SEQUENCE_S:
            etat = self.etat()
            # l'étape i se termine quand le directeur passe à i+1 : c'est le moment de mesurer,
            # pas après, sinon la mesure mélange l'arrivée et le départ suivant
            if etat["step"] > etape_vue:
                arrivees.append(self._mesurer(etape_vue))
                etape_vue = etat["step"]
            if etat["state"] in ("DONE", "FAILED", "CANCELLED", "CANCELLED_SAFETY"):
                break
            time.sleep(0.05)
        if etat["state"] == "DONE":
            while len(arrivees) < len(SEQUENCE):
                arrivees.append(self._mesurer(len(arrivees)))
        return {"depart": depart, "etat_final": etat, "arrivees": arrivees}

    def _mesurer(self, index: int) -> dict:
        nom = SEQUENCE[index]
        cible = self.catalogue.resoudre(nom)
        x, y, yaw = self.pose()
        return {"waypoint": nom, "cible": [cible.x, cible.y], "pose": [round(x, 3), round(y, 3),
                                                                      round(yaw, 3)],
                "ecart_m": round(math.hypot(x - cible.x, y - cible.y), 3)}

    def fermer(self):
        self._arrete.set()
        try:
            self._executeur.shutdown()
        finally:
            for noeud in (self.directeur, self.sonde, self.base):
                try:
                    noeud.destroy_node()
                except Exception:
                    pass
            rclpy.try_shutdown()


def demarrer_nav2() -> subprocess.Popen:
    environnement = dict(os.environ)
    environnement["ROS_DOMAIN_ID"] = "99"
    journal = JOURNAL_NAV2.open("w")
    return subprocess.Popen(
        ["ros2", "launch", str(RACINE / "launch" / "navigation.launch.py")],
        stdout=journal, stderr=subprocess.STDOUT, env=environnement, start_new_session=True)


def main() -> int:
    rclpy.init()
    nav2 = demarrer_nav2()
    preuve = Preuve()
    code = 1
    try:
        delai = preuve.attendre_nav2()
        print(f"Nav2 pret en {delai:.1f} s (journal : {JOURNAL_NAV2})")
        resultat = preuve.jouer()

        print("\n=== arrivees mesurees (base virtuelle vs catalogue) ===")
        for arrivee in resultat["arrivees"]:
            verdict = "OK" if arrivee["ecart_m"] <= TOLERANCE_M else "HORS TOLERANCE"
            print(f"  {arrivee['waypoint']:8s} pose {arrivee['pose']} "
                  f"cible {arrivee['cible']} ecart {arrivee['ecart_m']:.3f} m  {verdict}")
        etat = resultat["etat_final"]
        print(f"\netat final : {etat['state']} etape {etat['step']}/{etat['steps']} "
              f"motif {etat['reason']}")

        complet = (etat["state"] == "DONE" and etat["step"] == etat["steps"] == len(SEQUENCE))
        atteints = [a for a in resultat["arrivees"] if a["ecart_m"] <= TOLERANCE_M]
        if complet and len(atteints) == len(SEQUENCE):
            print("\nRESULTAT : 3 waypoints nommes atteints a +/-20 cm, get_task montre les etapes.")
            print("Reste a valider sur le robot : adherence, temps mort du MCU (0,85 s), "
                  "glissement Mecanum, et la justesse d'AMCL sur un scan reel.")
            code = 0
        else:
            print(f"\nRESULTAT : ECHEC — {len(atteints)}/{len(SEQUENCE)} waypoints dans la "
                  f"tolerance, etat {etat['state']}")
    except Exception as erreur:      # noqa: BLE001 — on veut le rapport, pas la trace seule
        print(f"\nRESULTAT : ECHEC — {type(erreur).__name__}: {erreur}")
        code = 1
    finally:
        preuve.fermer()
        try:
            os.killpg(os.getpgid(nav2.pid), 15)
        except ProcessLookupError:
            pass
        nav2.wait(timeout=20)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
