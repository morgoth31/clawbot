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


# Signe du retour encodeur. L'inversion observée venait de la trame : le driver annonçait
# car_type=1 (X3, moteurs 370) alors que le châssis est un X3 Plus (moteurs 520). Avec
# car_type=2 dans la trame ET en EEPROM, le STM32 renvoie un signe positif natif (mesuré
# le 2026-11-11 : échelon +0,05 -> retour positif, sans emballement). Aucune correction.
FEEDBACK_SIGN = 1.0


def feedback(value: float) -> float:
    """Vitesse mesurée remise dans la convention ROS (avance = +x)."""
    return _finite(value) * FEEDBACK_SIGN


#: pas de rampe par appel de commande (m/s). À 10-20 Hz, cela borne l'accélération demandée
#: et empêche l'intégrateur du STM32 de windup pendant le temps mort de friction statique.
RAMP_STEP = 0.02


def ramp_cmd(prev, target, max_delta=RAMP_STEP):
    """Approche la consigne par petits pas au lieu d'un échelon."""
    out = []
    for p, t in zip(prev, target):
        delta = max(-max_delta, min(max_delta, _finite(t) - _finite(p)))
        out.append(_finite(p) + delta)
    return tuple(out)
