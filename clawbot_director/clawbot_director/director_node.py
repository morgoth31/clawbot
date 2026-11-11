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
from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String

from clawbot_interfaces.srv import DirectorCommand

from .director import (ACCEPTED, Director, PRECONDITION_FAILED, RUNNING,
                       WAITING_CONFIRMATION)
from .skills import (SkillIndisponible, SkillInconnu, SkillInvalide,
                     construire_plan)

SAFETY_OK = "OK"
SAFETY_TIMEOUT_S = 1.0   # l'arbitre publie à 20 Hz : 1 s de silence = 20 messages manqués
STATE_PERIOD_S = 0.2     # 5 Hz, y compris sans changement
WATCHDOG_PERIOD_S = 0.1  # vérification des délais d'étape
MOTIF_PERIME = "safety_stale"

ETATS_GOAL = {
    GoalStatus.STATUS_SUCCEEDED: "succeeded",
    GoalStatus.STATUS_ABORTED: "aborted",
    GoalStatus.STATUS_CANCELED: "canceled",
    GoalStatus.STATUS_CANCELING: "canceling",
}


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
        self.create_timer(WATCHDOG_PERIOD_S, self.verifier_delai_etape)
        self._clients_action: dict[tuple[str, str], ActionClient] = {}
        self._etape = None          # goal en vol : plan, task_id, step, handle, deadline
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
            return self.annuler_tache(demande.get("reason") or "demande",
                                      demande.get("task_id") or None)
        if op == "confirm":
            accepte = demande.get("accepte")
            if not isinstance(accepte, bool):
                return {"status": "INVALID", "reason": "accepte doit etre un booleen"}
            return self.director.resume(accepte)
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
        # BUSY d'abord : la réponse à « puis-je démarrer ? » ne dépend pas du skill demandé,
        # et S2 doit recevoir le task_id courant, pas un refus sur le contenu de sa demande.
        etat = self.director.state()
        if etat["state"] in (RUNNING, WAITING_CONFIRMATION):
            return {"status": "BUSY", "task_id": etat["task_id"], "skill": etat["skill"]}
        # Une étape non exécutable est refusée avant que quoi que ce soit bouge : un skill
        # inconnu ou pas encore implémenté ne doit pas produire une tâche ACCEPTED fantôme.
        for etape in steps:
            try:
                construire_plan(etape)
            except SkillInconnu as exc:
                return {"status": "INVALID", "reason": str(exc)}
            except SkillInvalide as exc:
                return {"status": "INVALID", "reason": str(exc)}
            except SkillIndisponible as exc:
                return {"status": "INDISPONIBLE", "reason": str(exc)}
        reponse = self.director.start_sequence(steps)
        if reponse.get("status") == ACCEPTED:
            self._executer_etape()
        return reponse

    # ── exécution : un goal à la fois, advance() sur le résultat ─────────
    def _client_action(self, plan) -> ActionClient:
        cle = (plan.action, plan.type_action.__name__)
        client = self._clients_action.get(cle)
        if client is None:
            client = ActionClient(self, plan.type_action, plan.action)
            self._clients_action[cle] = client
        return client

    def _executer_etape(self):
        etat = self.director.state()
        if etat["state"] != RUNNING:
            return
        etape = self.director.current_step()
        if etape is None:
            return
        try:
            plan = construire_plan(etape)
        except (SkillInconnu, SkillInvalide, SkillIndisponible) as exc:
            self.director.advance(False, str(exc))
            self.publish_state()
            return

        client = self._client_action(plan)
        if not client.server_is_ready():
            self.director.advance(False, f"action indisponible : {plan.action}")
            self.publish_state()
            return

        suivi = {"plan": plan, "task_id": etat["task_id"], "step": etat["step"],
                 "handle": None, "deadline": time.monotonic() + plan.timeout_s}
        self._etape = suivi
        futur = client.send_goal_async(plan.goal)
        futur.add_done_callback(lambda f: self._goal_repondu(f, suivi))
        self.get_logger().info(
            f"etape {suivi['step']} : {etat['skill']} -> {plan.action} "
            f"(delai {plan.timeout_s:g} s)")

    def _goal_repondu(self, futur, suivi):
        handle = futur.result()
        perime = self._etape is not suivi
        if handle is not None and handle.accepted and (perime or suivi.get("annule")):
            # annulation demandée avant que le handle n'existe : on la rattrape ici
            self._annuler_goal(handle)
            return
        if perime:
            return
        if handle is None or not handle.accepted:
            self._terminer_etape(suivi, False, "goal refuse")
            return
        suivi["handle"] = handle
        handle.get_result_async().add_done_callback(lambda f: self._resultat(f, suivi))

    def _resultat(self, futur, suivi):
        if self._etape is not suivi:
            return   # étape annulée ou périmée : le résultat tardif ne compte pas
        statut = futur.result().status
        succes = statut == GoalStatus.STATUS_SUCCEEDED
        motif = "" if succes else f"goal {ETATS_GOAL.get(statut, statut)}"
        self._terminer_etape(suivi, succes, motif)

    def _terminer_etape(self, suivi, succes: bool, motif: str):
        if self._etape is suivi:
            self._etape = None
        etat = self.director.state()
        if etat["state"] != RUNNING or etat["task_id"] != suivi["task_id"] \
                or etat["step"] != suivi["step"]:
            self.publish_state()
            return
        reponse = self.director.advance(succes, motif)
        if not succes:
            self.get_logger().warning(f"etape {suivi['step']} echouee : {motif}")
        if reponse.get("status") == RUNNING:
            self._executer_etape()
        else:
            self.publish_state()

    def verifier_delai_etape(self):
        """Un goal qui ne rend jamais la main ne bloque pas la tâche : on annule et on échoue."""
        suivi = self._etape
        if suivi is None or time.monotonic() <= suivi["deadline"]:
            return
        self._etape = None
        if suivi["handle"] is not None:
            self._annuler_goal(suivi["handle"])
        etat = self.director.state()
        if etat["state"] == RUNNING and etat["task_id"] == suivi["task_id"] \
                and etat["step"] == suivi["step"]:
            self.director.advance(False, "TIMEOUT")
            self.get_logger().warning(
                f"etape {suivi['step']} : TIMEOUT apres {suivi['plan'].timeout_s:g} s, goal annule")
        self.publish_state()

    def _annuler_etape(self):
        suivi = self._etape
        self._etape = None
        if suivi is None:
            return
        suivi["annule"] = True
        if suivi["handle"] is not None:
            self._annuler_goal(suivi["handle"])

    @staticmethod
    def _annuler_goal(handle):
        futur = handle.cancel_goal_async()

        def _consommer(reponse):
            try:
                reponse.result()
            except Exception:   # le sort du goal est déjà tranché ailleurs
                pass

        futur.add_done_callback(_consommer)

    def annuler_tache(self, motif: str, task_id: str | None = None) -> dict:
        """Annule la tâche et, si un goal est en vol, le goal lui-même."""
        resultat = self.director.cancel(task_id, reason=motif)
        if resultat.get("status") in ("CANCELLED", "CANCELLED_SAFETY"):
            self._annuler_etape()
        return resultat

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
        resultat = self.annuler_tache(motif)
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
