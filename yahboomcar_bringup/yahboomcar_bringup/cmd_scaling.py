"""Mise à l'échelle des commandes de vitesse — logique pure, testable hors ROS.

La carte Rosmaster attend des m/s et des rad/s, pas des unités internes. ERR-009 vient de deux
choses distinctes : un seuil mort dans le MCU qui ignore les petites consignes, et un gain
d'échelle entre la consigne et la vitesse réelle. Ce module traite la première, borne la seconde,
et laisse le gain mesurable (`LINEAR_GAIN`, `ANGULAR_GAIN`) pour l'étalonnage physique.
"""

DEADBAND_RATIO = 0.02   # 2 % de la commande max : sous ce seuil le MCU n'agit pas
MAX_LINEAR = 0.35       # m/s, butée logicielle du X3 Plus
MAX_ANGULAR = 2.0       # rad/s

# Gains à ajuster après la mesure physique des 2 m (Tâche 1.2). 1.0 = pas de correction.
LINEAR_GAIN = 1.0
ANGULAR_GAIN = 1.0


def _finite(value: float) -> float:
    """Une valeur NaN ou infinie ne doit jamais atteindre le MCU."""
    if value is None:
        return 0.0
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        return 0.0
    return value


def scale_linear(value: float, gain: float = LINEAR_GAIN) -> float:
    """Consigne linéaire bornée et sortie de la bande morte, en m/s."""
    value = _finite(value) * gain
    if abs(value) <= MAX_LINEAR * DEADBAND_RATIO:
        return 0.0
    return max(-MAX_LINEAR, min(MAX_LINEAR, value))


def scale_angular(value: float, gain: float = ANGULAR_GAIN) -> float:
    """Consigne angulaire bornée et sortie de la bande morte, en rad/s."""
    value = _finite(value) * gain
    if abs(value) <= MAX_ANGULAR * DEADBAND_RATIO:
        return 0.0
    return max(-MAX_ANGULAR, min(MAX_ANGULAR, value))


def scale_cmd_vel(vx: float, vy: float, wz: float) -> tuple[float, float, float]:
    """Trame prête pour `set_car_motion(vx, vy, wz)`."""
    return scale_linear(vx), scale_linear(vy), scale_angular(wz)
