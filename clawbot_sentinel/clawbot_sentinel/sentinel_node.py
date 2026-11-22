"""Sentinel S1 : filtre d'attention, mots d'arrêt locaux et réveil de S2.

Trois responsabilités, aucune planification :

  - **voir** : YOLO à 1 Hz + profondeur Astra ; une personne n'engage que si sa confiance dépasse
    0,75, sa distance 3,5 m, et qu'elle est vue sur deux frames consécutives ;
  - **entendre** : « stop », « arrête-toi », « halte » coupent la tâche et remettent la consigne
    à zéro sans passer par S2 ; « oui »/« non » ne sont consommés qu'en `WAITING_CONFIRMATION` ;
  - **réveiller** : une transition d'état ou une fin de tâche produit **un** POST vers la
    passerelle Hermes, jamais un flux. Anti-rebond de 2 s sur les fins de tâche.

Le nœud ne publie jamais sur `/cmd_vel_safe` (propriété de l'arbitre) : l'arrêt local publie une
consigne nulle sur `/cmd_vel`, l'entrée de l'arbitre, exactement comme un opérateur.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String

from clawbot_interfaces.srv import DirectorCommand

from .attention import ENGAGED, IDLE, Attention
from .depth import distance_au_centre
from .words import NON, OUI, STOP, intention

YOLO_URL = "http://127.0.0.1:8003/detect_raw"
CONFIANCE_MIN = 0.75
DISTANCE_MAX_M = 3.5
PERIODE_SONDE_S = 1.0
PERIODE_APPLICATION_S = 0.5
ANTI_REBOND_FIN_S = 2.0
ETATS_TERMINAUX = {"DONE", "FAILED", "CANCELLED", "CANCELLED_SAFETY"}
WAITING_CONFIRMATION = "WAITING_CONFIRMATION"


class SentinelNode(Node):
    def __init__(self, sondeur=None, distanceur=None, declencheur=None):
        super().__init__("sentinel")
        self.attention = Attention()
        self._sondeur = sondeur or self._sondeur_http
        self._distanceur = distanceur or self._distanceur_image
        self._declencheur = declencheur or self._declencheur_hermes

        self._observation = None       # (personne, distance_m)
        self._derniere_personne = None
        self._directeur_etat = {}
        self._derniere_tache_terminale = None
        self._dernier_reveil_terminal = 0.0
        self._profondeur = None        # dernier Image de profondeur
        self._arret = threading.Event()
        self._fil = None

        self.pub_state = self.create_publisher(String, "/sentinel/state", 10)
        self.pub_event = self.create_publisher(String, "/sentinel/event", 10)
        self.pub_cmd = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(String, "/sentinel/transcript", self.on_transcript, 10)
        self.create_subscription(String, "/director/state", self.on_director_state, 10)
        self.create_subscription(Image, "/camera/depth/image_raw", self.on_profondeur,
                                 qos_profile_sensor_data)
        self.client_directeur = self.create_client(DirectorCommand, "/director/command")

        self.create_timer(PERIODE_APPLICATION_S, self.tick)
        self._fil = threading.Thread(target=self._boucle_sonde, daemon=True)
        self._fil.start()
        self.publish_state()

    # ── capteurs ─────────────────────────────────────────────────────────
    def _boucle_sonde(self):
        while not self._arret.is_set():
            try:
                detections = self._sondeur() or []
                personne, distance = self._juger(detections)
                self._observation = (personne, distance)
                if personne:
                    self._derniere_personne = time.monotonic()
            except Exception as exc:   # un capteur qui tombe ne doit pas tuer le sentinel
                self.get_logger().warning(f"sonde visuelle en echec : {exc}")
                self._observation = (False, None)
            self._arret.wait(PERIODE_SONDE_S)

    def _juger(self, detections):
        """Une personne retenue : confiance suffisante, distance mesurée et proche."""
        meilleure = None
        for detection in detections:
            if detection.get("label") != "person":
                continue
            confiance = float(detection.get("confidence") or 0.0)
            if confiance < CONFIANCE_MIN:
                continue
            distance = detection.get("distance_m")
            if distance is None:
                distance = self._distanceur(detection.get("bbox") or [])
            if distance is None or float(distance) > DISTANCE_MAX_M:
                continue
            if meilleure is None or confiance > meilleure[0]:
                meilleure = (confiance, float(distance))
        if meilleure is None:
            return False, None
        return True, meilleure[1]

    def _sondeur_http(self):
        with urllib.request.urlopen(YOLO_URL, timeout=2.0) as reponse:
            charge = json.loads(reponse.read().decode())
        return charge.get("detections") or []

    def _distanceur_image(self, bbox):
        image = self._profondeur
        if image is None or not bbox:
            return None
        try:
            from cv_bridge import CvBridge
            donnees = CvBridge().imgmsg_to_cv2(image, desired_encoding="passthrough")
        except Exception as exc:
            self.get_logger().warning(f"profondeur illisible : {exc}")
            return None
        return distance_au_centre(donnees, image.encoding, bbox)

    def on_profondeur(self, msg):
        self._profondeur = msg

    # ── boucle d'application ─────────────────────────────────────────────
    def tick(self):
        observation = self._observation
        if observation is not None:
            personne, distance = observation
            for evenement in self.attention.voir(personne):
                if evenement["type"] == "REVEIL":
                    self.reveiller(evenement["source"], {"distance_m": distance})
        self.publish_state()

    # ── parole ──────────────────────────────────────────────────────────
    def on_transcript(self, msg):
        voulu = intention(msg.data)
        if voulu is None:
            return
        if voulu == STOP:
            self.arreter_localement("voix_arret")
            return
        etat = (self._directeur_etat or {}).get("state")
        if etat == WAITING_CONFIRMATION:
            self.appeler_directeur({"op": "confirm", "accepte": voulu == OUI},
                                   f"voix_{voulu.lower()}")
        else:
            self.get_logger().info(
                f"« {msg.data[:40]} » laisse a S2 : le directeur n attend pas de confirmation")

    def arreter_localement(self, motif: str):
        self.pub_cmd.publish(Twist())      # priorite 0,5 : même effet qu'un opérateur
        self.appeler_directeur({"op": "cancel_task", "reason": motif}, motif)
        self.publier_evenement({"type": "ARRET_LOCAL", "motif": motif,
                                "at": round(time.time(), 3)})

    # ── directeur ───────────────────────────────────────────────────────
    def appeler_directeur(self, charge: dict, contexte: str):
        if not self.client_directeur.service_is_ready():
            self.get_logger().warning(f"{contexte} : /director/command indisponible")
            self.publier_evenement({"type": "DIRECTEUR_INDISPONIBLE", "contexte": contexte,
                                    "at": round(time.time(), 3)})
            return
        requete = DirectorCommand.Request()
        requete.request_json = json.dumps(charge, ensure_ascii=False)
        futur = self.client_directeur.call_async(requete)
        futur.add_done_callback(lambda f: self._reponse_directeur(f, contexte))

    def _reponse_directeur(self, futur, contexte):
        try:
            reponse = json.loads(futur.result().response_json)
        except Exception as exc:   # le service a répondu, mais pas ce qu'on attendait
            self.get_logger().warning(f"{contexte} : reponse illisible ({exc})")
            return
        self.get_logger().info(f"{contexte} -> {reponse.get('status')}")
        self.publier_evenement({"type": "DIRECTEUR", "contexte": contexte,
                                "status": reponse.get("status"),
                                "at": round(time.time(), 3)})

    def on_director_state(self, msg):
        try:
            etat = json.loads(msg.data)
        except ValueError:
            return
        self._directeur_etat = etat
        self.surveiller_fin_de_tache(etat)

    def surveiller_fin_de_tache(self, etat: dict):
        nom = etat.get("state")
        tache = etat.get("task_id")
        if nom not in ETATS_TERMINAUX or not tache:
            return
        if tache == self._derniere_tache_terminale:
            return
        maintenant = time.monotonic()
        if maintenant - self._dernier_reveil_terminal < ANTI_REBOND_FIN_S:
            return
        self._dernier_reveil_terminal = maintenant
        self._derniere_tache_terminale = tache
        self.reveiller("TASK_TERMINAL", {"task_id": tache, "state": nom,
                                         "reason": etat.get("reason")})

    # ── réveil et publication ───────────────────────────────────────────
    def reveiller(self, source: str, donnees: dict):
        personne = self.attention.etat == ENGAGED
        age = None
        if self._derniere_personne is not None:
            age = round(time.monotonic() - self._derniere_personne, 1)
        evenement = {
            "trigger_type": "EVENT_WAKEUP",
            "source": source,
            "timestamp": round(time.time(), 3),
            "event_data": donnees,
            "robot_snapshot": {
                "visible_person": personne,
                "seconds_since_person": age,
                "director_state": (self._directeur_etat or {}).get("state"),
                "attention": self.attention.etat,
            },
        }
        livre = False
        try:
            livre = bool(self._declencheur(evenement))
        except Exception as exc:
            self.get_logger().warning(f"reveil {source} non delivre : {exc}")
        self.publier_evenement({"type": "REVEIL", "source": source, "delivered": livre,
                                "event_data": donnees, "at": round(time.time(), 3)})
        if livre:
            self.get_logger().info(f"reveil S2 envoye ({source})")

    def _declencheur_hermes(self, evenement: dict) -> bool:
        """Voie webhook : un POST signé, jamais un réveil par frame."""
        try:
            from bridge_mcp.hermes_trigger import TriggerError, post_webhook
        except ImportError as exc:
            self.get_logger().warning(f"hermes_trigger introuvable : {exc}")
            return False
        source = evenement.get("source")
        question = (f"Evenement S1 {source}. Rends compte en une phrase, sans action."
                    if source == "TASK_TERMINAL" else
                    f"Evenement S1 {source}. Engage la conversation si un humain est present.")
        try:
            resultat = post_webhook({"event": evenement}, question, urgency="normale")
        except TriggerError as exc:
            self.get_logger().warning(f"reveil webhook refuse : {exc}")
            return False
        except (urllib.error.URLError, OSError) as exc:
            self.get_logger().warning(f"reveil webhook injoignable : {exc}")
            return False
        return bool(resultat.get("ok"))

    def publier_evenement(self, evenement: dict):
        self.pub_event.publish(String(data=json.dumps(evenement, ensure_ascii=False)))

    def etat(self) -> dict:
        age = None
        if self._derniere_personne is not None:
            age = round(time.monotonic() - self._derniere_personne, 1)
        return {"state": self.attention.etat,
                "person_seen": self.attention.etat == ENGAGED,
                "person_age_s": age,
                "director_state": (self._directeur_etat or {}).get("state"),
                "depth_available": self._profondeur is not None,
                "published_at": round(time.time(), 3)}

    def publish_state(self):
        self.pub_state.publish(String(data=json.dumps(self.etat(), ensure_ascii=False)))

    def fermer(self):
        self._arret.set()


def main():
    rclpy.init()
    node = SentinelNode()
    node.get_logger().info("sentinel pret")
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.fermer()
        node.destroy_node()
        rclpy.try_shutdown()
    return 0
