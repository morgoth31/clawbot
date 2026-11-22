"""Lecture entrelacée des servos du bras.

Une lecture de servo est bloquante (~15-20 ms sur le bus UART du Rosmaster). Six lectures
synchrones coûteraient 90-120 ms et casseraient la boucle de /imu et /vel_raw à 10 Hz dont dépend
l'EKF. On lit donc un servo par tick, et on ne lit presque rien quand le bras est au repos.
"""


class RoundRobin:
    def __init__(self, servo_ids=(1, 2, 3, 4, 5, 6), idle_period_ticks=10):
        self.ids = list(servo_ids)
        self.idle_period_ticks = idle_period_ticks
        self._i = 0
        self._idle = 0

    def next_servo(self, arm_at_rest=False):
        """Identifiant du servo à lire maintenant, ou None si on saute ce tick."""
        if arm_at_rest and (self._idle % self.idle_period_ticks):
            self._idle += 1
            return None
        self._idle += 1
        sid = self.ids[self._i % len(self.ids)]
        self._i += 1
        return sid

    def cycle_ticks(self):
        """Nombre de ticks pour un cycle complet des six servos."""
        return len(self.ids)
