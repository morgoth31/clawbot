"""Observations de référence pour les tests de déclenchement.

`nominal()` décrit un robot sain **tel qu'il est réellement au 2026-11-10** : les absences
constatées (`/scan`, `/odom`, `base_link`, `odom`, `map`, jauge d'énergie) ne sont pas des
pannes mais l'état de référence (contraintes C-01 à C-03).
"""

from __future__ import annotations

from bridge_mcp.observations import (
    EndpointObs,
    GoalFailure,
    LogEntry,
    NodeObs,
    Observation,
    ResourceObs,
    TopicObs,
)


def nominal(now: float = 1000.0) -> Observation:
    """Observation d'un robot sain, hors absences structurelles connues."""
    return Observation(
        nodes=[
            NodeObs("/driver_node", alive=True),
            NodeObs("/camera/camera", alive=True),
        ],
        topics=[
            TopicObs("/voltage", declared_period_s=0.1, age_s=0.05, rate_hz=10.0, nominal_rate_hz=10.0),
            TopicObs("/camera/color/image_raw", declared_period_s=0.05, age_s=0.02, rate_hz=20.0, nominal_rate_hz=20.0),
        ],
        services=[EndpointObs("/driver_node/set_parameters", available=True)],
        actions=[],
        tf_ages={"camera_link": 0.02, "camera_color_frame": 0.02},
        resources=ResourceObs(
            voltage_v=11.9,
            disk_free_gb=12.0,
            thermal_c={"cpu": 52.9, "tj": 53.0, "gpu": 50.5},
            memory_available_mb=4000,
        ),
        watchdog_stops=[],
        last_command_at=None,
    )


# ---------------------------------------------------------------- défauts injectés
def node_missing(obs: Observation, now: float) -> Observation:
    obs.nodes[0] = NodeObs("/driver_node", alive=False, missing_for_s=4.0)
    return obs


def service_unavailable(obs: Observation, now: float) -> Observation:
    obs.services[0] = EndpointObs("/driver_node/set_parameters", available=False, unavailable_for_s=3.0)
    return obs


def topic_silent(obs: Observation, now: float) -> Observation:
    # période déclarée 0,1 s : le seuil est 3 périodes = 0,3 s
    obs.topics[0] = TopicObs("/voltage", 0.1, age_s=0.9, rate_hz=0.0, nominal_rate_hz=10.0)
    return obs


def topic_slow(obs: Observation, now: float) -> Observation:
    # cadence 3 Hz contre 10 Hz nominaux : 30 % < 50 %
    obs.topics[0] = TopicObs("/voltage", 0.1, age_s=0.2, rate_hz=3.0, nominal_rate_hz=10.0)
    return obs


def qos_incompatible(obs: Observation, now: float) -> Observation:
    obs.topics[0] = TopicObs("/voltage", 0.1, age_s=0.05, rate_hz=10.0, nominal_rate_hz=10.0, qos_incompatible=True)
    return obs


def tf_stale(obs: Observation, now: float) -> Observation:
    # `base_link` est requis mais absent : contrainte C-02
    obs.tf_ages.pop("base_link", None)
    obs.tf_ages["camera_link"] = 1.4
    return obs


def thermal_hot(obs: Observation, now: float) -> Observation:
    obs.resources = ResourceObs(
        voltage_v=11.9, disk_free_gb=12.0, thermal_c={"cpu": 74.5, "tj": 53.0}, memory_available_mb=4000
    )
    return obs


def voltage_low(obs: Observation, now: float) -> Observation:
    obs.resources = ResourceObs(
        voltage_v=10.8, disk_free_gb=12.0, thermal_c={"cpu": 52.9}, memory_available_mb=4000
    )
    return obs


def disk_full(obs: Observation, now: float) -> Observation:
    obs.resources = ResourceObs(
        voltage_v=11.9, disk_free_gb=4.2, thermal_c={"cpu": 52.9}, memory_available_mb=4000
    )
    return obs


def goal_failed(obs: Observation, now: float) -> Observation:
    obs.failed_goals = [GoalFailure(action="/navigate_to_pose", goal_id="g-17", status="aborted")]
    return obs


def watchdog_repeated(obs: Observation, now: float) -> Observation:
    obs.watchdog_stops = [now - 12.0, now - 2.0]
    obs.last_command_at = now - 40.0
    return obs


def tool_failures(obs: Observation, now: float) -> Observation:
    obs.tool_failures = [("param_set", now - 50.0), ("param_set", now - 20.0), ("param_set", now - 1.0)]
    return obs


def unhandled_exception(obs: Observation, now: float) -> Observation:
    obs.unhandled_exceptions = [
        LogEntry(at=now - 0.5, level="error", node="/driver_node", message="KeyError: 'serial_port'")
    ]
    return obs


def unknown_condition(obs: Observation, now: float) -> Observation:
    obs.unknown_conditions = ["capteur_ultrason_arriere: echo bloqué haut"]
    return obs


FAULTS = {
    "TRG-01": node_missing,
    "TRG-02": service_unavailable,
    "TRG-03": topic_silent,
    "TRG-04": topic_slow,
    "TRG-05": qos_incompatible,
    "TRG-06": tf_stale,
    "TRG-07": thermal_hot,
    "TRG-08": voltage_low,
    "TRG-09": disk_full,
    "TRG-10": goal_failed,
    "TRG-11": watchdog_repeated,
    "TRG-12": tool_failures,
    "TRG-13": unhandled_exception,
    "TRG-14": unknown_condition,
}
