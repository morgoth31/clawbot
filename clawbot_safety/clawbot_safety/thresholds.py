"""Seuils de sécurité du Système 1 — logique pure, sans ROS, testable hors robot.

Chaque fonction répond à une seule question et ne lit rien : l'arbitre (tâche 2.3) collecte les
mesures, ces fonctions décident. Un angle invalide n'est jamais une valeur : il est traité comme
une condition d'arrêt, parce qu'un servo débranché renvoyait -5° sans que rien ne le signale.
"""

from __future__ import annotations

HOLD_DEG = 8.0            # au-delà : on annule la trajectoire et on maintient le couple
DROP_DEG = 12.0          # au-delà : on coupe le couple, si la géométrie le permet
SERVO2_FORWARD_MAX = 95.0  # sous 95° le bras est en extension avant : la chute va vers le sol
OBSTACLE_M = 0.15
BATTERY_FLOOR = 10.5
STALE_S = 2.0


def _valide(*valeurs: float) -> bool:
    for v in valeurs:
        if v is None or v != v or v in (float("inf"), float("-inf")):
            return False
    return True


def tilt_state(roll_deg: float, pitch_deg: float, servo2_deg: float) -> str:
    """État de basculement : ok, hold (maintien), drop_torque, ou freeze.

    La coupure de couple n'est autorisée que si le bras pointe vers l'avant (servo 2 < 95°) :
    relevé vers l'arrière, la chute par gravité irait contre le mât (seuil de collision 114°),
    et le réflexe devient un maintien figé.
    """
    if not _valide(roll_deg, pitch_deg, servo2_deg):
        return "hold"
    if servo2_deg < 0 or servo2_deg > 180:
        return "hold"
    inclinaison = max(abs(roll_deg), abs(pitch_deg))
    if inclinaison >= DROP_DEG:
        return "drop_torque" if servo2_deg < SERVO2_FORWARD_MAX else "freeze"
    if inclinaison >= HOLD_DEG:
        return "hold"
    return "ok"


def obstacle_stop(front_m: float, cmd_nonzero: bool) -> bool:
    """Vrai s'il faut écraser la consigne : obstacle proche ET le robot veut bouger."""
    if not _valide(front_m):
        return bool(cmd_nonzero)   # lidar muet : on ne roule pas à l'aveugle
    return bool(cmd_nonzero) and front_m < OBSTACLE_M


def battery_state(samples: list[float], now_s: float, window_s: float = 10.0,
                  spike_s: float = 2.0) -> str:
    """ok ou low. Un pic de courant de moins de 2 s ne doit pas condamner la batterie."""
    valeurs = [v for v in samples if _valide(v)]
    if not valeurs:
        return "low"
    derniere = valeurs[-1]
    if derniere >= BATTERY_FLOOR:
        return "ok"
    # chute franche : on regarde si elle dure. La fenêtre de 10 s est échantillonnée à 10 Hz.
    profondeur = int(window_s * 10)
    historique = valeurs[-profondeur:]
    sous_seuil = sum(1 for v in historique if v < BATTERY_FLOOR)
    duree_s = sous_seuil / 10.0
    return "low" if duree_s >= spike_s else "ok"


def is_stale(age_s: float, limit_s: float = STALE_S) -> bool:
    """Un flux muet est une condition d'arrêt, jamais un silence."""
    if not _valide(age_s):
        return True
    return age_s > limit_s
