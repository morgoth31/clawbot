"""Observation du robot telle que S1 la collecte à chaque cycle (entrée des déclencheurs).

Structure volontairement passive : ce module ne lit rien, il décrit. L'adaptateur ROS 2
remplira ces structures ; les tests les construisent à la main.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NodeObs:
    name: str
    alive: bool
    missing_for_s: float = 0.0


@dataclass
class TopicObs:
    name: str
    declared_period_s: float
    age_s: float
    rate_hz: float
    nominal_rate_hz: float
    qos_incompatible: bool = False


@dataclass
class EndpointObs:
    """Service ou action du graphe."""

    name: str
    available: bool
    unavailable_for_s: float = 0.0


@dataclass
class GoalFailure:
    action: str
    goal_id: str
    status: str  # aborted | canceled | rejected
    expected: bool = False


@dataclass
class LogEntry:
    at: float
    level: str
    node: str
    message: str


@dataclass
class ResourceObs:
    voltage_v: float | None
    disk_free_gb: float
    thermal_c: dict[str, float] = field(default_factory=dict)
    memory_available_mb: int = 0


@dataclass
class Observation:
    """État mesuré du robot à un instant donné."""

    nodes: list[NodeObs] = field(default_factory=list)
    topics: list[TopicObs] = field(default_factory=list)
    services: list[EndpointObs] = field(default_factory=list)
    actions: list[EndpointObs] = field(default_factory=list)
    tf_ages: dict[str, float] = field(default_factory=dict)
    resources: ResourceObs = field(default_factory=lambda: ResourceObs(voltage_v=None, disk_free_gb=0.0))
    failed_goals: list[GoalFailure] = field(default_factory=list)
    watchdog_stops: list[float] = field(default_factory=list)
    last_command_at: float | None = None
    tool_failures: list[tuple[str, float]] = field(default_factory=list)
    unhandled_exceptions: list[LogEntry] = field(default_factory=list)
    unknown_conditions: list[str] = field(default_factory=list)
    recovery_resolved: list[tuple[str, str]] = field(default_factory=list)
