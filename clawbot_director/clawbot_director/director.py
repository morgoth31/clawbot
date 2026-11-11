"""Directeur du Système 1 : registre de tâche, préconditions, séquences.

Logique pure, sans ROS : le directeur décide QUAND un skill peut tourner, jamais CE QUE le robot
doit faire — c'est le rôle de S2, qui déclare une séquence. Ici on garantit trois choses :

  - un seul skill actif à la fois, avec un identifiant de tâche interrogeable ;
  - les préconditions sont vérifiées par S1, S2 n'est jamais cru (pince vide avant saisie,
    bras replié avant déplacement, tension suffisante) ;
  - une annulation se termine à un point sûr, donc entre deux étapes, jamais au milieu.
"""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

BUSY = "BUSY"
PRECONDITION_FAILED = "PRECONDITION_FAILED"
CANCELLED_SAFETY = "CANCELLED_SAFETY"
TIMEOUT = "TIMEOUT"
ACCEPTED = "ACCEPTED"
DONE = "DONE"
FAILED = "FAILED"
RUNNING = "RUNNING"
WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
IDLE = "IDLE"

MAX_STEPS = 6
HISTORY_SIZE = 20   # tâches terminées conservées pour get_task(task_id)


@dataclass
class Task:
    task_id: str
    skill: str
    args: dict
    state: str = RUNNING
    step: int = 0
    steps: list = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    history: list = field(default_factory=list)


class Director:
    """Un seul task actif ; les autres appels reçoivent BUSY avec l'identifiant courant."""

    def __init__(self, preconditions=None, clock=time.time):
        self._preconditions = preconditions or (lambda skill, args: (True, ""))
        self._clock = clock
        self._task: Task | None = None
        self._historique: OrderedDict[str, dict] = OrderedDict()

    # ── interrogation ─────────────────────────────────────────────────────
    def state(self) -> dict:
        """Jeu de clés fixe, que la tâche existe ou non : un contrat de supervision doit être
        typable. Les valeurs absentes sont nulles, pas omises."""
        if self._task is None:
            return {"state": IDLE, "task_id": None, "skill": None, "step": None,
                    "steps": 0, "elapsed_s": 0.0, "started_at": None, "reason": None}
        return self._instantane(self._task)

    def get(self, task_id: str) -> dict | None:
        """État d'une tâche, en cours ou terminée ; None si l'identifiant est inconnu.

        Une tâche terminée reste consultable (anneau borné) : S2 demande souvent « pourquoi
        annulé ? » après qu'une autre tâche a démarré.
        """
        if self._task is not None and self._task.task_id == task_id:
            return self._instantane(self._task)
        return self._historique.get(task_id)

    def _instantane(self, t: Task) -> dict:
        fin = t.finished_at or self._clock()
        return {"state": t.state, "task_id": t.task_id, "skill": t.skill,
                "step": t.step, "steps": len(t.steps),
                "elapsed_s": round(fin - t.started_at, 2),
                "started_at": t.started_at,
                "reason": t.history[-1].get("reason") if t.history else None}

    def _archiver(self):
        t = self._task
        if t is None:
            return
        self._historique[t.task_id] = self._instantane(t)
        while len(self._historique) > HISTORY_SIZE:
            self._historique.popitem(last=False)

    # ── démarrage ────────────────────────────────────────────────────────
    def start(self, skill: str, args: dict | None = None) -> dict:
        return self.start_sequence([{"skill": skill, "args": args or {}}])

    def start_sequence(self, steps: list) -> dict:
        if self._task is not None and self._task.state in (RUNNING, WAITING_CONFIRMATION):
            return {"status": BUSY, "task_id": self._task.task_id, "skill": self._task.skill}
        if not steps or len(steps) > MAX_STEPS:
            return {"status": PRECONDITION_FAILED,
                    "reason": f"sequence de 1 a {MAX_STEPS} etapes attendue"}
        premier = steps[0]
        ok, raison = self._preconditions(premier["skill"], premier.get("args") or {})
        if not ok:
            return {"status": PRECONDITION_FAILED, "reason": raison,
                    "skill": premier["skill"]}

        self._archiver()
        self._task = Task(
            task_id="t-" + uuid.uuid4().hex[:10],
            skill=premier["skill"],
            args=premier.get("args") or {},
            steps=list(steps),
            started_at=self._clock(),
        )
        self._task.history.append({"step": 0, "skill": premier["skill"], "state": RUNNING})
        return {"status": ACCEPTED, "task_id": self._task.task_id,
                "skill": premier["skill"], "steps": len(steps)}

    # ── progression ──────────────────────────────────────────────────────
    def advance(self, success: bool = True, reason: str = "") -> dict:
        """Appelée à la fin d'une étape : passe à la suivante ou termine la tâche."""
        t = self._task
        if t is None or t.state not in (RUNNING, WAITING_CONFIRMATION):
            return {"status": "NO_TASK"}
        t.history[-1]["result"] = success
        if not success:
            t.state = FAILED
            t.finished_at = self._clock()
            t.history[-1]["reason"] = reason
            return {"status": FAILED, "task_id": t.task_id, "step": t.step,
                    "reason": reason}

        t.step += 1
        if t.step >= len(t.steps):
            t.state = DONE
            t.finished_at = self._clock()
            return {"status": DONE, "task_id": t.task_id, "steps": len(t.steps)}

        suivant = t.steps[t.step]
        # point sûr : la précondition de l'étape suivante est vérifiée ici, après l'arrêt
        ok, refus = self._preconditions(suivant["skill"], suivant.get("args") or {})
        if not ok:
            t.state = FAILED
            t.finished_at = self._clock()
            t.history.append({"step": t.step, "skill": suivant["skill"],
                              "state": PRECONDITION_FAILED, "reason": refus})
            return {"status": PRECONDITION_FAILED, "task_id": t.task_id,
                    "step": t.step, "reason": refus}
        t.skill = suivant["skill"]
        t.args = suivant.get("args") or {}
        t.history.append({"step": t.step, "skill": t.skill, "state": RUNNING})
        return {"status": RUNNING, "task_id": t.task_id, "step": t.step,
                "skill": t.skill}

    def ask_confirmation(self) -> dict:
        """Le directeur attend un oui/non : seul état où S1 intercepte « oui » et « non »."""
        if self._task is None:
            return {"status": "NO_TASK"}
        self._task.state = WAITING_CONFIRMATION
        return {"status": WAITING_CONFIRMATION, "task_id": self._task.task_id}

    def resume(self, accepte: bool) -> dict:
        if self._task is None or self._task.state != WAITING_CONFIRMATION:
            return {"status": "NO_TASK"}
        if not accepte:
            self._task.state = CANCELLED_SAFETY
            self._task.finished_at = self._clock()
            return {"status": CANCELLED_SAFETY, "task_id": self._task.task_id}
        self._task.state = RUNNING
        return {"status": RUNNING, "task_id": self._task.task_id}

    # ── annulation ───────────────────────────────────────────────────────
    def cancel(self, task_id: str | None = None, reason: str = "demande") -> dict:
        """Annulation à un point sûr : la tâche passe à CANCELLED, aucune étape n'est lancée."""
        t = self._task
        if t is None:
            return {"status": "NO_TASK"}
        if task_id and task_id != t.task_id:
            return {"status": "UNKNOWN_TASK", "task_id": t.task_id}
        if t.state in (DONE, FAILED, CANCELLED_SAFETY):
            return {"status": t.state, "task_id": t.task_id}
        # Tout motif de la famille « safety » est une annulation de sécurité : le motif précis
        # (safety, safety_stale) est conservé dans l'historique, le code reste CANCELLED_SAFETY.
        t.state = CANCELLED_SAFETY if reason.startswith("safety") else "CANCELLED"
        t.finished_at = self._clock()
        t.history.append({"step": t.step, "skill": t.skill, "state": t.state,
                          "reason": reason})
        return {"status": t.state, "task_id": t.task_id, "step": t.step}
