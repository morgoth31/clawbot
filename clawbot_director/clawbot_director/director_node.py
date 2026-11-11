"""Nœud ROS du directeur : la logique pure de `director.py` branchée au graphe.

Le directeur décide quand un skill peut tourner, jamais ce que le robot doit faire. Ce nœud
ajoute ce que la logique pure ne peut pas voir : l'état de sécurité publié par l'arbitre sur
/safety/state. Deux règles non négociables :

  - aucune tâche ne démarre sans un OK **frais** — le silence de l'arbitre n'est pas un feu vert ;
  - dès que cet état sort de OK, ou que le flux se tait, la tâche en cours est annulée sans
    attendre le prochain point sûr.

/director/state publie un relevé daté : état de tâche, motif de la dernière transition, valeur
de sécurité lue, âge de cette valeur et péremption. Un relevé, jamais une conclusion.
"""

from __future__ import annotations

import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from clawbot_interfaces.srv import DirectorCommand

from .director import Director, PRECONDITION_FAILED

SAFETY_OK = "OK"
SAFETY_TIMEOUT_S = 1.0   # l'arbitre publie à 20 Hz : 1 s de silence = 20 messages manqués
STATE_PERIOD_S = 0.2     # 5 Hz, y compris sans changement
MOTIF_PERIME = "safety_stale"


class DirectorNode(Node):
    def __init__(self):
        super().__init__("director")
        self.director = Director()
        self.safety = None          # dernière valeur lue, None si l'arbitre n'a jamais parlé
        self.last_safety_t = None   # horloge monotone de la dernière lecture
        self._dernier_defaut = None  # dernier défaut déjà traité, pour ne pas répéter l'alerte

        self.pub_state = self.create_publisher(String, "/director/state", 10)
        self.create_subscription(String, "/safety/state", self.on_safety, 10)
        self.create_service(DirectorCommand, "/director/command", self.on_commande)
        self.create_timer(STATE_PERIOD_S, self.tick)
        self.publish_state()

    # ── surface de commande (ce que le pont MCP appelle) ─────────────────
    def on_commande(self, requete, reponse):
        reponse.response_json = json.dumps(self.commande(requete.request_json),
                                           ensure_ascii=False)
        return reponse

    def commande(self, texte: str) -> dict:
        """Une seule porte d'entrée : JSON en entrée, JSON en sortie, rien d'implicite."""
        try:
            demande = json.loads(texte)
        except (TypeError, ValueError) as exc:
            return {"status": "INVALID", "reason": f"requete JSON invalide : {exc}"}
        if not isinstance(demande, dict):
            return {"status": "INVALID", "reason": "objet JSON attendu"}

        op = demande.get("op")
        if op == "start_skill":
            return self._start_skill(demande)
        if op == "start_sequence":
            return self._start_sequence(demande)
        if op == "get_task":
            return self._get_task(demande)
        if op == "cancel_task":
            return self.director.cancel(demande.get("task_id") or None,
                                        reason=demande.get("reason") or "demande")
        return {"status": "INVALID", "reason": f"operation inconnue : {op!r}"}

    def _start_skill(self, demande):
        skill = demande.get("skill")
        if not isinstance(skill, str) or not skill.strip():
            return {"status": "INVALID", "reason": "skill attendu"}
        args = demande.get("args") or {}
        if not isinstance(args, dict):
            return {"status": "INVALID", "reason": "args doit etre un objet"}
        return self.start(skill.strip(), args)

    def _start_sequence(self, demande):
        steps = demande.get("steps")
        if not isinstance(steps, list) or not steps:
            return {"status": "INVALID", "reason": "steps doit etre une liste non vide"}
        for etape in steps:
            if not isinstance(etape, dict) or not isinstance(etape.get("skill"), str) \
                    or not etape["skill"].strip():
                return {"status": "INVALID", "reason": "chaque etape exige un skill"}
            if etape.get("args") is not None and not isinstance(etape["args"], dict):
                return {"status": "INVALID", "reason": "args d etape doit etre un objet"}
        return self.start_sequence([{"skill": e["skill"].strip(), "args": e.get("args") or {}}
                                    for e in steps])

    def _get_task(self, demande):
        task_id = demande.get("task_id") or ""
        if not task_id:
            return {"status": "FOUND", "task": self.etat()}
        trouvee = self.director.get(str(task_id))
        if trouvee is None:
            return {"status": "UNKNOWN_TASK", "task_id": task_id}
        return {"status": "FOUND", "task": trouvee}

    # ── entrée : la sécurité est une précondition, pas une réaction ─────
    def refus_securite(self) -> str:
        """Raison de refus si la sécurité n'est pas un OK frais, chaîne vide sinon."""
        if self.last_safety_t is None:
            return "securite inconnue : aucun message recu sur /safety/state"
        age = time.monotonic() - self.last_safety_t
        if age > SAFETY_TIMEOUT_S:
            return f"securite perimee : {age:.1f} s sans message (etat {self.safety})"
        if self.safety != SAFETY_OK:
            return f"securite {self.safety}"
        return ""

    def start(self, skill: str, args: dict | None = None) -> dict:
        return self.start_sequence([{"skill": skill, "args": args or {}}])

    def start_sequence(self, steps: list) -> dict:
        refus = self.refus_securite()
        if refus:
            return {"status": PRECONDITION_FAILED, "reason": refus}
        return self.director.start_sequence(steps)

    # ── sécurité ─────────────────────────────────────────────────────────
    def on_safety(self, msg):
        etat = msg.data.strip().upper()
        self.safety = etat
        self.last_safety_t = time.monotonic()
        if etat == SAFETY_OK:
            self._dernier_defaut = None
        elif etat != self._dernier_defaut:
            # traité une fois par valeur de défaut : un STOP à 20 Hz ne doit ni noyer le
            # journal ni faire mentir la cadence de /director/state
            self._dernier_defaut = etat
            self.annuler("safety", f"etat {etat}")

    def annuler(self, motif: str, contexte: str):
        resultat = self.director.cancel(reason=motif)
        if resultat.get("status") not in ("NO_TASK", "UNKNOWN_TASK"):
            self.get_logger().warning(
                f"{motif} — {contexte} : tache {resultat.get('task_id')} "
                f"-> {resultat.get('status')}")

    def tick(self):
        age = self.surveiller_peremption()
        self.publish_state()
        self._loguer_cadence(age)

    def surveiller_peremption(self):
        """Chien de garde : sans OK frais, on n'exécute pas. Le silence annule comme un défaut."""
        if self.last_safety_t is None:
            return None
        age = time.monotonic() - self.last_safety_t
        if age > SAFETY_TIMEOUT_S and self._dernier_defaut != MOTIF_PERIME:
            self._dernier_defaut = MOTIF_PERIME
            self.annuler(MOTIF_PERIME, f"flux muet, derniere valeur {self.safety or 'aucune'}")
        return age

    # ── sortie ──────────────────────────────────────────────────────────
    def etat(self) -> dict:
        age = None
        if self.last_safety_t is not None:
            age = round(time.monotonic() - self.last_safety_t, 3)
        etat = dict(self.director.state())
        etat.update({
            "safety": self.safety,
            "safety_age_s": age,
            "safety_stale": age is None or age > SAFETY_TIMEOUT_S,
            "published_at": round(time.time(), 3),
        })
        return etat

    def publish_state(self):
        # republié à chaque période, jamais seulement sur changement : un abonné tardif doit
        # voir l'état sans attendre un événement (un changement peut ne jamais venir).
        self.pub_state.publish(String(data=json.dumps(self.etat(), ensure_ascii=False)))

    def _loguer_cadence(self, age):
        self._n = getattr(self, "_n", 0) + 1
        if self._n % 300 == 0:   # toutes les minutes
            self.get_logger().info(
                f"etat={self.director.state()['state']} safety={self.safety} "
                f"age={age if age is None else round(age, 2)}")


def main():
    rclpy.init()
    node = DirectorNode()
    node.get_logger().info("directeur pret")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
