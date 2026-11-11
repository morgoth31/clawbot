import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_director.director import (  # noqa: E402
    ACCEPTED, BUSY, CANCELLED_SAFETY, DONE, FAILED, PRECONDITION_FAILED, RUNNING, Director,
)


def preconditions(skill, args):
    if skill == "grasp_object" and args.get("gripper") == "closed":
        return False, "pince non vide"
    return True, ""


def test_second_skill_is_refused_with_busy():
    d = Director(preconditions)
    premier = d.start("navigate_to", {"waypoint": "cuisine"})
    assert premier["status"] == ACCEPTED
    second = d.start("grasp_object", {})
    assert second["status"] == BUSY
    assert second["task_id"] == premier["task_id"]


def test_precondition_failure_blocks_start():
    d = Director(preconditions)
    refus = d.start("grasp_object", {"gripper": "closed"})
    assert refus["status"] == PRECONDITION_FAILED
    assert "pince" in refus["reason"]
    assert d.state()["state"] == "IDLE"


def test_three_step_sequence_runs_in_order():
    d = Director(preconditions)
    r = d.start_sequence([{"skill": "navigate_to", "args": {}},
                          {"skill": "grasp_object", "args": {}},
                          {"skill": "navigate_to", "args": {}}])
    assert r["status"] == ACCEPTED and r["steps"] == 3
    assert d.advance(True)["skill"] == "grasp_object"
    assert d.advance(True)["step"] == 2
    fin = d.advance(True)
    assert fin["status"] == DONE


def test_failure_mid_sequence_stops_the_task():
    d = Director(preconditions)
    d.start_sequence([{"skill": "a"}, {"skill": "b"}])
    r = d.advance(False, "blocage servo")
    assert r["status"] == FAILED and r["reason"] == "blocage servo"


def test_sequence_longer_than_six_is_refused():
    d = Director()
    r = d.start_sequence([{"skill": "x"}] * 7)
    assert r["status"] == PRECONDITION_FAILED


def test_cancel_is_immediate_and_named():
    d = Director()
    t = d.start("navigate_to", {})
    r = d.cancel(t["task_id"], reason="safety")
    assert r["status"] == CANCELLED_SAFETY
    assert d.state()["state"] == CANCELLED_SAFETY


def test_stale_safety_is_a_safety_cancellation_too():
    # le motif précis est conservé (« safety_stale »), le code reste CANCELLED_SAFETY
    d = Director()
    t = d.start("navigate_to", {})
    r = d.cancel(t["task_id"], reason="safety_stale")
    assert r["status"] == CANCELLED_SAFETY
    assert d.state()["reason"] == "safety_stale"


def test_state_has_a_stable_key_set_when_a_task_exists():
    d = Director()
    repos = d.state()
    d.start("navigate_to", {})
    actif = d.state()
    assert set(repos) == set(actif)
    assert actif["started_at"] > 0 and repos["started_at"] is None
    assert repos["steps"] == 0 and actif["steps"] == 1


def test_finished_task_stays_consultable_after_a_new_one_starts():
    # get_task(task_id) doit répondre après coup : une tâche terminée n'est pas effacée
    d = Director()
    t1 = d.start("navigate_to", {})["task_id"]
    d.cancel(t1, reason="safety")
    t2 = d.start("grasp_object", {})["task_id"]
    assert t2 != t1

    ancienne = d.get(t1)
    assert ancienne["task_id"] == t1
    assert ancienne["state"] == CANCELLED_SAFETY
    assert ancienne["reason"] == "safety"
    assert ancienne["skill"] == "navigate_to"
    assert ancienne["elapsed_s"] >= 0
    assert d.get(t2)["state"] == RUNNING


def test_unknown_task_is_not_invented():
    d = Director()
    assert d.get("t-inexistant") is None


def test_task_history_is_bounded():
    d = Director()
    premiers = []
    for i in range(25):
        tid = d.start("navigate_to", {"n": i})["task_id"]
        if i == 0:
            premiers.append(tid)
        d.cancel(tid)
    assert d.get(premiers[0]) is None, "la plus ancienne tache doit etre evincee"


def test_confirmation_is_the_only_place_yes_no_is_consumed():
    d = Director()
    d.start("grasp_object", {})
    assert d.ask_confirmation()["status"] == "WAITING_CONFIRMATION"
    assert d.resume(False)["status"] == CANCELLED_SAFETY
