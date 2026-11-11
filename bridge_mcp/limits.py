"""Limites effectives du pont, telles que S1 les applique (ressource `robot://limites`).

Ces valeurs proviennent de l'état constaté du robot, pas d'une hypothèse :
- `MAX_LINEAR_MS` / `MAX_ANGULAR_RS` : environnement de `ros2-hardware-service.service`
  (0.06 m/s et 0.25 rad/s) ;
- `motion_watchdog_s` : `MOTION_WATCHDOG_S=1.5` du même service ;
- `allowed_params` : paramètres déclarés par `Mcnamu_driver_X3` et bornés par le schéma d'outils ;
- `waypoints` / `navigation` : catalogue fermé et réglages Nav2 (lot 5, 2026-11-11) ;
- `unavailable` : données encore absentes du robot au 2026-11-11.
"""

from __future__ import annotations

import os
import sys
from typing import Any

# Le catalogue de waypoints est la seule énumération que S2 peut adresser. Il est lu depuis le
# fichier que le directeur utilise, pour que la liste annoncée à S2 ne puisse pas diverger de la
# liste appliquée. Une erreur de lecture ne doit pas vider la surface : on la rend visible.
try:                                   # pragma: no cover - dépend du déploiement
    _RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _RACINE not in sys.path:
        sys.path.insert(0, _RACINE)
    from clawbot_director import waypoints as _catalogue

    _CATALOGUE = _catalogue.charger()
    WAYPOINTS: dict[str, list[float]] = {
        nom: [waypoint.x, waypoint.y]
        for nom, waypoint in sorted(_CATALOGUE.waypoints.items())}
    CARTE_NAVIGATION = _CATALOGUE.carte
    ERREUR_CATALOGUE = ""
except Exception as _erreur:          # noqa: BLE001 - le pont doit rester interrogeable
    WAYPOINTS = {}
    CARTE_NAVIGATION = ""
    ERREUR_CATALOGUE = f"{type(_erreur).__name__}: {_erreur}"

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
    # Skills que S2 peut déclarer au directeur (§6 de la conception). Une chaîne libre est
    # refusée avant tout appel ROS : la surface d'édition de S2 est une énumération.
    "allowed_skills": [
        "navigate_to",
        "follow_human",
        "grasp_object",
        "search_object",
        "express_state",
        "look_at_board",
        "set_watch_mode",
    ],
    # Énumération fermée des destinations de `navigate_to` : nom -> [x, y] sur la carte ci-dessous.
    # Aucune coordonnée libre n'est acceptée ; `navigate_to` refuse tout nom absent de cette table.
    "waypoints": WAYPOINTS,
    "navigation": {
        "map": CARTE_NAVIGATION,
        "frame": "map",
        "action": "/navigate_to_pose",
        "xy_goal_tolerance_m": 0.12,
        "max_linear_ms": 0.10,
        "max_angular_rs": 0.30,
        "timeout_s": 90.0,
        "requires": ["/odom", "/scan", "tf map->odom->base_link"],
        "catalogue_error": ERREUR_CATALOGUE,
    },
    "s2_min_severity": 2,
    "budget": {"tool_calls": 8, "duration_s": 120},
    "protocol_version": "2025-11-25",
    "unavailable": [
        "etat de charge batterie: aucune jauge systeme (ENOENT)",
        "camera du poignet dans ROS: aucun noeud publie (lot 6)",
        "/sentinel/transcript: aucun producteur VAD/STT (lot 7)",
        "modele 3D du bras dans le costmap de Nav2: rayon d'encombrement seulement",
    ],
}

