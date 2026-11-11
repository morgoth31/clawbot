"""CTX-01 à CTX-06 : structure, complétude et bornes du contexte transmis à S2."""

from __future__ import annotations

import json

import pytest

from bridge_mcp import context, triggers
from support import observations
from support.fake_clock import FakeClock

pytestmark = pytest.mark.contract

REQUIRED_BLOCKS = {
    "schema_version",
    "incident_id",
    "created_at",
    "trigger",
    "robot",
    "graph",
    "tf",
    "diagnostics",
    "params",
    "resources",
    "limits",
    "unavailable",
}


def _incident(trigger_id: str = "TRG-03"):
    clock = FakeClock()
    engine = triggers.TriggerEngine(clock.now)
    for _ in range(60):
        observation = observations.FAULTS[trigger_id](observations.nominal(clock.now()), clock.now())
        emitted = engine.observe(observation, clock.now())
        if emitted:
            return engine, observation, engine.state.get(emitted[0].incident_id)
        clock.advance(0.1)
    raise AssertionError("aucun incident produit")


def test_context_contains_every_required_block():
    """CTX-01 : tous les blocs obligatoires sont présents, aucun n'est vide par accident."""
    engine, observation, incident = _incident()
    payload = context.build_context(incident, observation, engine.state)

    assert set(payload) >= REQUIRED_BLOCKS
    assert payload["schema_version"] == "1.0"
    assert payload["incident_id"] == incident.incident_id
    assert payload["trigger"]["id"] == "TRG-03"
    assert payload["trigger"]["severity"] == 2


def test_unavailable_data_is_declared_with_a_code():
    """CTX-02 : ce que l'observation ne contient pas est déclaré, avec un code stable."""
    engine, observation, incident = _incident()
    payload = context.build_context(incident, observation, engine.state)
    joined = " ".join(payload["unavailable"])

    for expected in ("/scan", "/odom", "base_link", "odom", "map"):
        assert expected in joined, f"{expected} doit être déclaré indisponible"
    assert "ROS2-TOPIC-ABSENT" in joined
    assert "TF-FRAME-MISSING" in joined


def test_les_absences_suivent_l_observation_et_non_une_liste_figee():
    """CTX-02b : un robot complet ne déclare aucune absence structurelle.

    La liste était codée en dur : elle annonçait `/scan`, `/odom` et les cadres `map`/`odom`/
    `base_link` absents alors que le robot les publie depuis le 2026-11-11. Une déclaration qui ne
    dépend pas de la mesure est fausse un jour sur deux.
    """
    engine, observation, incident = _incident()
    observation.topics.extend([
        observations.TopicObs("/scan", 0.1, 0.05, 10.0, 10.0),
        observations.TopicObs("/odom", 0.1, 0.05, 10.0, 10.0),
    ])
    observation.tf_ages.update({"base_link": 0.02, "odom": 0.02, "map": 0.05})

    payload = context.build_context(incident, observation, engine.state)

    assert payload["unavailable"] == [], payload["unavailable"]
    assert payload["tf"]["frames_expected_missing"] == []


def test_une_jauge_d_energie_absente_porte_son_code():
    """CTX-02c : la seule absence qui reste vraiment structurelle sur ce robot."""
    engine, observation, incident = _incident()
    observation.resources.voltage_v = None

    payload = context.build_context(incident, observation, engine.state)
    joined = " ".join(payload["unavailable"])

    assert "ENOENT" in joined
    assert "/voltage: ROS2-TOPIC-ABSENT" in joined


def test_context_is_bounded_in_size():
    """CTX-04 : le contexte reste sous 256 Ko, avec des listes bornées."""
    engine, observation, incident = _incident()
    for index in range(400):
        observation.topics.append(
            observations.TopicObs(f"/topic_{index}", 0.1, 0.05, 10.0, 10.0)
        )
    payload = context.build_context(incident, observation, engine.state)

    assert len(json.dumps(payload, ensure_ascii=False).encode()) <= 256 * 1024
    assert len(payload["graph"]["topics"]) <= 200
    assert len(payload["logs_tail"]) <= 200


def test_context_carries_no_secret():
    """CTX-06 : aucun jeton ni chemin de credentials dans le contexte."""
    engine, observation, incident = _incident()
    rendered = json.dumps(context.build_context(incident, observation, engine.state), ensure_ascii=False).lower()

    for forbidden in ("authorization", "bearer ", "token=", "password", "id_rsa", ".ssh/", "mcp-token"):
        assert forbidden not in rendered


def test_context_is_stable_between_reads():
    """CTX-05 : deux lectures sans évolution donnent le même contenu métier."""
    engine, observation, incident = _incident()
    first = context.build_context(incident, observation, engine.state)
    second = context.build_context(incident, observation, engine.state)

    first.pop("read_at", None)
    second.pop("read_at", None)
    assert first == second


def test_context_measures_carry_their_age():
    """CTX-03 : chaque mesure de topic porte un âge et une cadence."""
    engine, observation, incident = _incident()
    payload = context.build_context(incident, observation, engine.state)

    assert payload["graph"]["topics"], "au moins un topic mesuré"
    for topic in payload["graph"]["topics"]:
        assert "last_age_s" in topic
        assert "rate_hz" in topic
