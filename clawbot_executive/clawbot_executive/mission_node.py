"""Nœud exécutif de mission (REQ-EXEC-010 à 017).

`/clawbot/execute_mission` enchaîne des étapes via `/clawbot/execute_skill`, applique
la reprise et les budgets, suspend la mission en attente de décision, et journalise.
"""
from __future__ import annotations

import json
import queue
import threading
import traceback
import uuid
from pathlib import Path

import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from clawbot_common.errors import category, rapport_echec
from clawbot_interfaces.action import ExecuteMission, ExecuteSkill
from clawbot_interfaces.msg import MissionEvent
from clawbot_interfaces.srv import GetMissionReport, SubmitDecision

from .journal import Journal
from .mission import (DELAI_DECISION_S, DUREE_DEFAUT_S, MAX_ETAPES, EtatMission, Etape,
                      Issue, Mission, TERMINAUX)

REGISTRE_PAR_DEFAUT = "/home/jetson/clawbot/install/clawbot_executive/share/clawbot_executive/config/skills.yaml"
JOURNAL_PAR_DEFAUT = "/var/lib/clawbot/missions"
OUTCOME = {EtatMission.SUCCEEDED: 0, EtatMission.FAILED: 1,
           EtatMission.CANCELED: 2, EtatMission.ABORTED: 1}


class MissionExecutive(Node):
    def __init__(self, registre: str | Path | None = None, journal_dir: str | Path | None = None,
                 demarrer: bool = False, client_skills=None, nom: str = "mission_executive"):
        super().__init__(nom)
        self.declare_parameter("registre", REGISTRE_PAR_DEFAUT)
        self.declare_parameter("journal_dir", JOURNAL_PAR_DEFAUT)
        self.declare_parameter("decision_timeout_s", DELAI_DECISION_S)
        self.declare_parameter("max_duration_s", DUREE_DEFAUT_S)
        self.declare_parameter("period_s", 0.1)

        self.registre = str(registre or self.get_parameter("registre").value)
        self.journal_dir = Path(str(journal_dir or self.get_parameter("journal_dir").value))
        self.decision_timeout_s = float(self.get_parameter("decision_timeout_s").value)
        self.max_duration_s = float(self.get_parameter("max_duration_s").value)

        self._mission: Mission | None = None
        self._derniere: Mission | None = None
        self._verrou = threading.Lock()
        # Code du dernier refus de goal, lu par les tests et le journal (REQ-EXEC-021).
        self.dernier_refus = ""
        # Le service ne modifie jamais la mission : il dépose un ordre, le fil qui fait
        # avancer la mission l'applique. Un seul propriétaire de l'état, donc aucun
        # croisement entre la décision et la boucle d'exécution.
        self._ordres: "queue.Queue[tuple]" = queue.Queue()
        self._decision = threading.Event()
        self._sante: dict = {"level": "OK", "active_capabilities": [], "stale_flows": [],
                             "safety_state": "UNKNOWN", "estop_latched": False, "voltage": 0.0}
        self._events_publies = 0

        groupe_etats = MutuallyExclusiveCallbackGroup()
        try:
            from clawbot_interfaces.msg import RobotHealth

            self.create_subscription(RobotHealth, "/clawbot/health", self._sur_sante, 10,
                                     callback_group=groupe_etats)
        except ImportError:                        # pragma: no cover
            self.get_logger().warn("RobotHealth absent : rapport sans instantané de santé")

        self.pub_events = self.create_publisher(MissionEvent, "/clawbot/mission/events", 20)
        self.cli_skills = client_skills or ActionClient(
            self, ExecuteSkill, "/clawbot/execute_skill")

        self.srv_decide = self.create_service(SubmitDecision, "/clawbot/mission/decide",
                                              self._sur_decide, callback_group=groupe_etats)
        self.srv_report = self.create_service(GetMissionReport, "/clawbot/mission/report",
                                              self._sur_report, callback_group=groupe_etats)
        self.action = ActionServer(
            self, ExecuteMission, "/clawbot/execute_mission",
            execute_callback=self._executer_mission,
            goal_callback=self._sur_goal,
            cancel_callback=lambda _g: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

        self.get_logger().info(f"mission_executive pret (journal {self.journal_dir})")
        self._executeur = None
        self._fil = None
        if demarrer:
            self._executeur = MultiThreadedExecutor(num_threads=4)
            self._executeur.add_node(self)
            self._fil = threading.Thread(target=self._executeur.spin, daemon=True)
            self._fil.start()

    # ── santé ────────────────────────────────────────────────────────────────
    def _sur_sante(self, msg) -> None:
        niveau = {0: "OK", 1: "WARN", 2: "ERROR"}.get(int(msg.level), "OK")
        self._sante = {"level": niveau,
                       "active_capabilities": list(msg.active_capabilities),
                       "stale_flows": list(msg.stale_flows),
                       "safety_state": msg.safety_state,
                       "estop_latched": bool(msg.estop_latched),
                       "voltage": float(msg.voltage)}

    # ── appel d'un skill ─────────────────────────────────────────────────────
    def appeler_skill(self, etape: Etape, timeout_s: float = 60.0) -> Issue:
        if not self.cli_skills.wait_for_server(timeout_sec=10.0):
            return Issue(ok=False, error_code="SKILL_SERVER_UNAVAILABLE",
                         message="/clawbot/execute_skill injoignable")
        goal = ExecuteSkill.Goal()
        goal.mission_id = self._mission.mission_id if self._mission else ""
        goal.skill = etape.skill
        goal.params_json = json.dumps(etape.params or {}, ensure_ascii=False)
        goal.timeout_s = float(etape.timeout_s or 0.0)

        futur = self.cli_skills.send_goal_async(goal)
        if not self._attendre(futur, 20.0):
            return Issue(ok=False, error_code="TIMEOUT", message="envoi du goal sans réponse")
        handle = futur.result()
        if not handle.accepted:
            return Issue(ok=False, error_code="UNKNOWN_SKILL", message="goal refusé")

        resultat = handle.get_result_async()
        if not self._attendre(resultat, timeout_s):
            return Issue(ok=False, error_code="TIMEOUT",
                         message=f"aucun résultat en {timeout_s:.0f} s")
        result = resultat.result().result
        if result.outcome == 0:
            return Issue(ok=True, result=json.loads(result.result_json or "{}"))
        return Issue(ok=False, error_code=result.error_code or "UNHANDLED_EXCEPTION",
                     message=result.message, result=json.loads(result.result_json or "{}"))

    @staticmethod
    def _attendre(futur, limite_s: float) -> bool:
        import time as _time

        fin = _time.monotonic() + limite_s
        while not futur.done() and _time.monotonic() < fin:
            _time.sleep(0.02)
        return futur.done()

    # ── rapport d'échec ──────────────────────────────────────────────────────
    def construire_rapport(self, issue: Issue, etape: Etape | None, mission: Mission) -> dict:
        try:
            return rapport_echec(
                mission_id=mission.mission_id, objective=mission.objective,
                step_index=mission.index, skill=(etape.skill if etape else ""),
                params=(etape.params if etape else {}), error_code=issue.error_code,
                message=issue.message, health=self._sante,
                budget={"escalations_left": mission.escalations_left,
                        "same_step_attempts_left": 2,
                        "time_left_s": max(0.0, mission.max_duration_s
                                           - (mission.horloge() - mission.debut))})
        except KeyError:
            return {"schema": "clawbot.failure_report/1", "mission_id": mission.mission_id,
                    "error_code": issue.error_code, "error_category": "",
                    "message": issue.message, "allowed_decisions": []}

    # ── actions ──────────────────────────────────────────────────────────────
    def _sur_goal(self, _goal_request):
        with self._verrou:
            if self._mission is not None and self._mission.etat not in TERMINAUX:
                return GoalResponse.REJECT
            # Sans serveur de skills, aucune mission ne peut aboutir : on refuse au lieu
            # d'accepter puis d'échouer étape par étape (REQ-EXEC-021). Le test est non
            # bloquant et se refait à chaque goal : dès que le serveur revient, la mission
            # suivante est acceptée, sans relance automatique.
            if not self._serveur_de_skills_pret():
                self.dernier_refus = "SKILL_SERVER_UNAVAILABLE"
                self.get_logger().warning(
                    "mission refusee : /clawbot/execute_skill absent "
                    "(SKILL_SERVER_UNAVAILABLE)")
                return GoalResponse.REJECT
            self.dernier_refus = ""
            return GoalResponse.ACCEPT

    def _serveur_de_skills_pret(self) -> bool:
        """Présence du serveur de skills, sans attente et sans lever d'exception."""
        try:
            return bool(self.cli_skills.server_is_ready())
        except Exception:  # noqa: BLE001 — un client factice peut ne pas l'implémenter
            return False

    def _executer_mission(self, goal_handle):
        requete = goal_handle.request
        resultat = ExecuteMission.Result()

        try:
            etapes_brutes = json.loads(requete.steps_json or "[]")
        except ValueError as exc:
            return self._rejeter(goal_handle, resultat, f"steps_json illisible : {exc}")
        if not isinstance(etapes_brutes, list) or not 1 <= len(etapes_brutes) <= MAX_ETAPES:
            return self._rejeter(goal_handle, resultat,
                                 f"1 à {MAX_ETAPES} étapes attendues")
        etapes = []
        for entree in etapes_brutes:
            if not isinstance(entree, dict) or "skill" not in entree:
                return self._rejeter(goal_handle, resultat, "étape sans champ « skill »")
            etapes.append(Etape(skill=str(entree["skill"]),
                                params=dict(entree.get("params") or {}),
                                timeout_s=float(entree.get("timeout_s", 0.0))))

        mission_id = requete.mission_id or str(uuid.uuid4())
        journal = Journal(mission_id, dossier=self.journal_dir)
        mission = Mission(mission_id, requete.objective, etapes, self.appeler_skill,
                          journal=journal, max_escalations=requete.max_escalations,
                          max_duration_s=requete.max_duration_s,
                          decision_timeout_s=self.decision_timeout_s,
                          rapport=self.construire_rapport)
        with self._verrou:
            self._mission = mission
        self._events_publies = 0
        self._publier_evenements(mission)

        try:
            mission.run()
            self._publier_evenements(mission)
            self._publier_feedback(goal_handle, mission)

            while mission.etat == EtatMission.WAITING_DECISION:
                if goal_handle.is_cancel_requested:
                    mission.annuler()
                    break
                self._decision.wait(timeout=0.05)
                self._decision.clear()
                self._appliquer_ordres(mission)
                self._publier_evenements(mission)
                if mission.etat == EtatMission.WAITING_DECISION:
                    if mission.verifier_delai_decision():
                        self._publier_evenements(mission)
                        break
                if mission.etat == EtatMission.RUNNING:
                    mission.run()
                    self._publier_evenements(mission)
                    self._publier_feedback(goal_handle, mission)

            if goal_handle.is_cancel_requested and mission.etat not in TERMINAUX:
                mission.annuler()
        except Exception as exc:                  # noqa: BLE001 - jamais de résultat vide
            self.get_logger().error(f"mission : exception {exc}\n{traceback.format_exc()}")
            mission.forcer_etat(EtatMission.FAILED, f"exception interne : {exc}")
            self._erreur_interne = str(exc)[:300]
        finally:
            journal.fermer()
            with self._verrou:
                self._derniere = mission
                self._mission = None
            self._publier_evenements(mission)

        resultat.mission_id = mission_id
        resultat.state = mission.etat.value
        resultat.outcome = OUTCOME.get(mission.etat, 1)
        resultat.failure_report_json = (json.dumps(mission.dernier_rapport, ensure_ascii=False)
                                       if mission.dernier_rapport else "")
        resume = mission.rapport()
        if getattr(self, "_erreur_interne", None):
            resume["internal_error"] = self._erreur_interne
            self._erreur_interne = None
        resultat.summary_json = json.dumps(resume, ensure_ascii=False)
        if mission.etat == EtatMission.SUCCEEDED:
            goal_handle.succeed()
        elif mission.etat == EtatMission.CANCELED:
            goal_handle.canceled()
        else:
            goal_handle.abort()
        return resultat

    def _rejeter(self, goal_handle, resultat, message: str):
        resultat.outcome = 3
        resultat.state = EtatMission.PENDING.value
        resultat.mission_id = goal_handle.request.mission_id
        resultat.summary_json = json.dumps({"error": message}, ensure_ascii=False)
        goal_handle.abort()
        return resultat

    def _publier_feedback(self, goal_handle, mission: Mission) -> None:
        retour = ExecuteMission.Feedback()
        retour.step_index = mission.index
        retour.step_count = len(mission.etapes)
        retour.state = mission.etat.value
        retour.current_skill = (mission.etapes[mission.index].skill
                                if mission.index < len(mission.etapes) else "")
        retour.progress = (mission.index / len(mission.etapes)) if mission.etapes else 0.0
        try:
            goal_handle.publish_feedback(retour)
        except Exception:                          # noqa: BLE001 - goal déjà clos
            pass

    def _publier_evenements(self, mission: Mission) -> None:
        for entree in mission.historique[self._events_publies:]:
            message = MissionEvent()
            message.stamp = self.get_clock().now().to_msg()
            message.mission_id = mission.mission_id
            message.event = entree["event"]
            message.detail_json = json.dumps(entree.get("detail", {}), ensure_ascii=False)
            try:
                self.pub_events.publish(message)
            except Exception:                      # noqa: BLE001 - nœud en cours de destruction
                return
        self._events_publies = len(mission.historique)

    # ── services ─────────────────────────────────────────────────────────────
    def _sur_decide(self, requete, reponse):
        mission = self._mission or self._derniere
        if mission is None:
            reponse.accepted = False
            reponse.message = "aucune mission"
            return reponse
        try:
            params = json.loads(requete.params_json or "{}") if requete.params_json else {}
        except ValueError as exc:
            reponse.accepted = False
            reponse.message = f"params_json illisible : {exc}"
            return reponse
        accepte, message = mission.verifier_decision(requete.decision, params,
                                                     requete.rationale)
        reponse.accepted = accepte
        reponse.message = message
        reponse.escalations_left = max(0, mission.escalations_left - (1 if accepte else 0))
        if accepte:
            self._ordres.put((requete.decision, params, requete.rationale))
            self._decision.set()
        return reponse

    def _appliquer_ordres(self, mission: Mission) -> None:
        """Applique les décisions déposées par le service, dans ce fil uniquement."""
        while True:
            try:
                decision, params, rationale = self._ordres.get_nowait()
            except queue.Empty:
                return
            accepte, message = mission.decider(decision, params, rationale)
            if not accepte:
                self.get_logger().warn(f"décision {decision} refusée à l'application : {message}")

    def _sur_report(self, requete, reponse):
        mission = self._mission
        if mission is None and requete.mission_id:
            if self._derniere and self._derniere.mission_id == requete.mission_id:
                mission = self._derniere
        else:
            mission = mission or self._derniere
        if mission is None:
            reponse.found = False
            reponse.report_json = "{}"
            return reponse
        reponse.found = True
        reponse.report_json = json.dumps(mission.rapport(), ensure_ascii=False)
        return reponse

    def destroy_node(self):
        if self._executeur is not None:
            self._executeur.shutdown(timeout_sec=2.0)
            self._executeur = None
        super().destroy_node()


def main(argv=None) -> int:
    from rclpy.executors import ExternalShutdownException

    rclpy.init(args=argv)
    noeud = None
    try:
        noeud = MissionExecutive()
        executeur = MultiThreadedExecutor(num_threads=4)
        executeur.add_node(noeud)
        executeur.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if noeud is not None:
            noeud.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
