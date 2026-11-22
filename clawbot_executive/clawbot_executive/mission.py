"""Machine d'états des missions : étapes, reprise, budgets, décision (REQ-EXEC-010 à 015).

Logique pure : l'exécuteur de skills est injecté (scripté dans les tests), l'horloge
aussi, et le journal est optionnel. Aucune dépendance à rclpy.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum

from clawbot_common.errors import allowed_decisions, auto_retry, category

MAX_ETAPES = 20
PLAFOND_ESCALADES = 3
PLAFOND_DUREE_S = 1800.0
DUREE_DEFAUT_S = 600.0
DELAI_DECISION_S = 120.0
TENTATIVES_MAX = 2


class EtatMission(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_DECISION = "WAITING_DECISION"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    CANCELED = "CANCELED"


TERMINAUX = (EtatMission.SUCCEEDED, EtatMission.FAILED,
             EtatMission.ABORTED, EtatMission.CANCELED)


@dataclass
class Etape:
    skill: str
    params: dict = field(default_factory=dict)
    timeout_s: float = 0.0

    def cle(self) -> str:
        return f"{self.skill}:{json.dumps(self.params, sort_keys=True)}"


@dataclass
class Issue:
    """Résultat d'une exécution de skill, vu par la machine."""
    ok: bool
    error_code: str = ""
    message: str = ""
    result: dict = field(default_factory=dict)


class Mission:
    """Une mission = une suite d'étapes, des budgets, des décisions."""

    def __init__(self, mission_id: str, objective: str, etapes: list[Etape],
                 executer, journal=None, horloge=time.monotonic,
                 max_escalations: int = PLAFOND_ESCALADES,
                 max_duration_s: float = DUREE_DEFAUT_S,
                 decision_timeout_s: float = DELAI_DECISION_S,
                 rapport=None):
        if not 1 <= len(etapes) <= MAX_ETAPES:
            raise ValueError(f"1 à {MAX_ETAPES} étapes attendues, {len(etapes)} reçues")
        self.mission_id = mission_id
        self.objective = objective
        self.etapes = list(etapes)
        self.executer = executer
        self.journal = journal
        self.horloge = horloge
        self.rapport_echec = rapport

        # budgets : un goal ne peut pas acheter plus que le référentiel (§6.3)
        self.max_escalations = min(int(max_escalations or PLAFOND_ESCALADES), PLAFOND_ESCALADES)
        self.escalations_left = self.max_escalations
        self.max_duration_s = min(float(max_duration_s or DUREE_DEFAUT_S), PLAFOND_DUREE_S)
        self.decision_timeout_s = float(decision_timeout_s)
        self.attempts: dict[str, int] = {}

        self.etat = EtatMission.PENDING
        self.index = 0
        self.debut = self.horloge()
        self.echeance_decision: float | None = None
        self.decisions: list[dict] = []
        self.dernier_rapport: dict | None = None
        self.historique: list[dict] = []
        self.resultats: list[dict] = []

    # ── journal ──────────────────────────────────────────────────────────────
    def evenement(self, nom: str, detail: dict | None = None) -> None:
        charge = {"mission_id": self.mission_id, "event": nom, "detail": detail or {}}
        self.historique.append(charge)
        if self.journal is not None:
            self.journal.ecrire(nom, detail or {})

    def _poser(self, etat: EtatMission) -> None:
        if self.etat != etat:
            self.etat = etat

    # ── exécution ────────────────────────────────────────────────────────────
    def run(self) -> None:
        """Exécute les étapes jusqu'à un état terminal ou WAITING_DECISION."""
        if self.etat == EtatMission.PENDING:
            self._poser(EtatMission.RUNNING)
            self.evenement("STARTED", {"objective": self.objective})
        while self.etat == EtatMission.RUNNING:
            if self.duree_depassee():
                self._abandonner("max_duration_s atteint")
                return
            if self.index >= len(self.etapes):
                self._poser(EtatMission.SUCCEEDED)
                self.evenement("SUCCEEDED", {"steps": len(self.resultats)})
                return
            self._executer_etape(self.etapes[self.index])

    def _executer_etape(self, etape: Etape) -> None:
        self.evenement("STEP_STARTED", {"index": self.index, "skill": etape.skill,
                                        "params": etape.params})
        issue = self.executer(etape)
        if issue.ok:
            self.resultats.append({"index": self.index, "skill": etape.skill,
                                   "result": issue.result})
            self.evenement("STEP_SUCCEEDED", {"index": self.index, "skill": etape.skill})
            self.index += 1
            return

        # échec : reprise automatique exactement selon la table (§6.1)
        auto = auto_retry(issue.error_code) if issue.error_code else (0, 0.0)
        tentatives, delai = auto
        deja = self.attempts.get(etape.cle(), 0)
        self.attempts[etape.cle()] = deja + 1
        peut_relancer = (tentatives > 0 and deja < tentatives
                         and self.attempts[etape.cle()] < TENTATIVES_MAX)
        self.evenement("STEP_FAILED", {"index": self.index, "skill": etape.skill,
                                       "error_code": issue.error_code,
                                       "attempt": self.attempts[etape.cle()],
                                       "auto_retry": peut_relancer})
        if peut_relancer:
            if delai:
                self.attendre(delai)
            self.evenement("RETRY", {"index": self.index, "delay_s": delai,
                                     "error_code": issue.error_code})
            return

        self._suspendre(issue)

    def _suspendre(self, issue: Issue) -> None:
        """Échec persistant : WAITING_DECISION + rapport + stop."""
        self.dernier_rapport = self._construire_rapport(issue)
        self._poser(EtatMission.WAITING_DECISION)
        self.echeance_decision = self.horloge() + self.decision_timeout_s
        self.evenement("WAITING_DECISION", {"index": self.index, "skill": self.etapes[self.index].skill
                                            if self.index < len(self.etapes) else "",
                                            "error_code": issue.error_code})
        self.evenement("FAILED", {"error_code": issue.error_code, "waiting": True})
        self.executer(Etape(skill="stop", params={}))       # robot à l'arrêt
        self._fermer_journal()

    # ── décisions ────────────────────────────────────────────────────────────
    def decider(self, decision: str, params: dict | None = None,
                rationale: str = "") -> tuple[bool, str]:
        if self.etat != EtatMission.WAITING_DECISION:
            return False, f"aucune décision attendue (état {self.etat.value})"
        code = (self.dernier_rapport or {}).get("error_code", "")
        autorisees = allowed_decisions(code) if code else ()
        if decision not in autorisees:
            return False, (f"décision {decision} hors allowed_decisions "
                           f"{list(autorisees)} — budget inchangé")
        if not rationale.strip():
            return False, "rationale obligatoire"

        self.decisions.append({"decision": decision, "params": params or {},
                               "rationale": rationale})
        if self.journal is not None:
            self.journal.ecrire("DECISION", {"decision": decision,
                                             "params": params or {}, "rationale": rationale})
        self.historique.append({"mission_id": self.mission_id, "event": "DECISION",
                                "detail": {"decision": decision, "rationale": rationale}})
        self.echeance_decision = None

        if decision == "ABORT":
            self._poser(EtatMission.ABORTED)
            self.evenement("ABORTED", {"decision": "ABORT"})
            self._fermer_journal()
            return True, "mission abandonnée"

        if decision == "REPLACE_REMAINING":
            nouvelles = self._valider_etapes(params)
            if nouvelles is None:
                return False, "REPLACE_REMAINING : étapes invalides (1 à 20, skills connus)"
            self.etapes = nouvelles
            self.index = 0

        # §6.3 : 2 tentatives au total par étape et paramètres, relance comprise
        if decision in ("RETRY_STEP", "RETRY_WITH_PARAMS") and self.index < len(self.etapes):
            etape = self.etapes[self.index]
            nouveaux = dict(params) if (decision == "RETRY_WITH_PARAMS" and params) else dict(etape.params)
            cle = f"{etape.skill}:{json.dumps(nouveaux, sort_keys=True)}"
            if self.attempts.get(cle, 0) >= TENTATIVES_MAX:
                return False, (f"tentatives épuisées pour {etape.skill} avec ces paramètres "
                               f"({TENTATIVES_MAX} au total)")

        if self.escalations_left <= 0:
            self._abandonner("plus d'escalade disponible")
            return False, "plus d'escalade disponible"
        self.escalations_left -= 1

        if decision == "RETRY_WITH_PARAMS" and params:
            etape = self.etapes[self.index] if self.index < len(self.etapes) else None
            if etape is not None:
                etape.params = dict(params)

        self._poser(EtatMission.RUNNING)
        self.evenement("RUNNING", {"decision": decision, "escalations_left": self.escalations_left})
        return True, f"décision {decision} acceptée"

    def _valider_etapes(self, params: dict | None) -> list[Etape] | None:
        brut = (params or {}).get("steps") if isinstance(params, dict) else None
        if not isinstance(brut, list) or not 1 <= len(brut) <= MAX_ETAPES:
            return None
        etapes = []
        for entree in brut:
            if not isinstance(entree, dict) or "skill" not in entree:
                return None
            etapes.append(Etape(skill=str(entree["skill"]),
                                params=dict(entree.get("params") or {}),
                                timeout_s=float(entree.get("timeout_s", 0.0))))
        return etapes

    # ── budgets ──────────────────────────────────────────────────────────────
    def duree_depassee(self, maintenant: float | None = None) -> bool:
        return ((maintenant or self.horloge()) - self.debut) > self.max_duration_s

    def delai_decision_depasse(self, maintenant: float | None = None) -> bool:
        if self.etat != EtatMission.WAITING_DECISION or self.echeance_decision is None:
            return False
        return (maintenant or self.horloge()) >= self.echeance_decision

    def verifier_delai_decision(self, maintenant: float | None = None) -> bool:
        if self.delai_decision_depasse(maintenant):
            self._abandonner("aucune décision dans le délai imparti")
            return True
        return False

    def attendre(self, duree_s: float) -> None:
        if duree_s > 0:
            time.sleep(min(float(duree_s), 5.0))

    def annuler(self) -> None:
        if self.etat in TERMINAUX:
            return
        self._poser(EtatMission.CANCELED)
        self.evenement("CANCELED", {"index": self.index})
        self.executer(Etape(skill="stop", params={}))
        self._fermer_journal()

    def _abandonner(self, raison: str) -> None:
        self._poser(EtatMission.ABORTED)
        self.evenement("ABORTED", {"reason": raison})
        self._fermer_journal()

    def _fermer_journal(self) -> None:
        if self.journal is not None:
            self.journal.fermer()

    # ── rapport ──────────────────────────────────────────────────────────────
    def _construire_rapport(self, issue: Issue) -> dict:
        etape = self.etapes[self.index] if self.index < len(self.etapes) else None
        if self.rapport_echec is not None:
            document = self.rapport_echec(issue, etape, self)
        else:
            document = {"schema": "clawbot.failure_report/1", "mission_id": self.mission_id,
                        "error_code": issue.error_code,
                        "error_category": category(issue.error_code) if issue.error_code else "",
                        "message": issue.message, "allowed_decisions":
                        list(allowed_decisions(issue.error_code)) if issue.error_code else []}
        if self.journal is not None:
            self.journal.ecrire("REPORT", document)
        return document

    def rapport(self) -> dict:
        etape = self.etapes[self.index] if self.index < len(self.etapes) else None
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "state": self.etat.value,
            "step_index": self.index,
            "step_count": len(self.etapes),
            "current_skill": etape.skill if etape else "",
            "steps": self.resultats,
            "failure_report": self.dernier_rapport,
            "decisions": self.decisions,
            "budget": {
                "escalations_left": self.escalations_left,
                "same_step_attempts_left": max(0, TENTATIVES_MAX - max(
                    [self.attempts.get(e.cle(), 0) for e in self.etapes] or [0])),
                "time_left_s": max(0.0, self.max_duration_s - (self.horloge() - self.debut)),
            },
            "events": self.historique[-10:],
        }

    def resume(self) -> dict:
        return {"mission_id": self.mission_id, "state": self.etat.value,
                "steps": len(self.resultats), "step_count": len(self.etapes),
                "escalations_left": self.escalations_left}
