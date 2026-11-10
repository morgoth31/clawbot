"""Limites effectives du pont, telles que S1 les applique (ressource `robot://limites`).

Ces valeurs proviennent de l'état constaté du robot, pas d'une hypothèse :
- `MAX_LINEAR_MS` / `MAX_ANGULAR_RS` : environnement de `ros2-hardware-service.service`
  (0.06 m/s et 0.25 rad/s) ;
- `motion_watchdog_s` : `MOTION_WATCHDOG_S=1.5` du même service ;
- `allowed_params` : paramètres déclarés par `Mcnamu_driver_X3` et bornés par le schéma d'outils ;
- `unavailable` : données absentes du robot au 2026-11-10 (voir base de connaissances OKF).
"""

from __future__ import annotations

from typing import Any

LIMITS: dict[str, Any] = {
    "max_linear_ms": 0.06,
    "max_angular_rs": 0.25,
    "motion_watchdog_s": 1.5,
    "max_motion_duration_s": 10.0,
    "allowed_params": [
        "angular_limit",
        "xlinear_limit",
        "ylinear_limit",
    ],
    # Action deplacements autorises pour goal_send : les deux controleurs du bras.
    # Les bornes articulaires sont verifiees dans ros_layer.ACTION_SPECS.
    "allowed_actions": [
        "/arm_controller/follow_joint_trajectory",
        "/grip_controller/follow_joint_trajectory",
    ],
    "s2_min_severity": 2,
    "budget": {"tool_calls": 8, "duration_s": 120},
    "protocol_version": "2025-11-25",
    "unavailable": [
        "/scan: aucune source laser (ROS2-TOPIC-ABSENT)",
        "/odom: topic absent (ROS2-TOPIC-ABSENT)",
        "base_link/odom/map: cadres TF absents (TF-FRAME-MISSING)",
        "etat de charge batterie: aucune jauge systeme (ENOENT)",
    ],
}
