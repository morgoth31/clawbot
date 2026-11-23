"""Covariances de l'IMU du MCU (REQ-DRV-014).

Le pilote publiait un `Imu()` dont tous les `*_covariance` restaient a zero — la valeur par
defaut du message. En robot_localization, une variance nulle signifie « mesure parfaite » :
l'EKF faisait une confiance infinie a un gyrometre a 10 Hz, sans rien pour contrebalancer sa
derive. Et `orientation_covariance[0] = 0` declarait une orientation valide alors que le
pilote ne la calcule pas.

Module pur, sans ROS : il est teste directement.
"""
from __future__ import annotations

#: Variance du taux de lacet mesure, (rad/s)^2. Mesure au repos du 2026-11-23 : le gyroscope
#: rend -0,001 rad/s avec des valeurs qui varient de quelques 1e-3 ; a 10 Hz et sur plusieurs
#: secondes, une variance de 1e-4 rad^2/s^2 reste prudente sans rendre la mesure inutile.
VARIANCE_GYRO = 1e-4

#: Variance des accelerations, (m/s^2)^2. La carte mesure un biais de 0,26 et 0,15 m/s^2 sur
#: x et y au repos : la variance doit couvrir ce biais, sinon le filtre le prendrait pour un
#: mouvement reel.
VARIANCE_ACCEL = 4e-2


def diagonale(*variances: float) -> list[float]:
    """Matrice 3x3 de covariance en liste ligne-major (9 valeurs)."""
    if len(variances) != 3:
        raise ValueError("trois variances attendues")
    for index, valeur in enumerate(variances):
        if not valeur > 0.0:
            raise ValueError(f"variance {index} non strictement positive : {valeur}")
    matrice = [0.0] * 9
    for index, valeur in enumerate(variances):
        matrice[index * 4] = float(valeur)
    return matrice


def covariance_orientation() -> list[float]:
    """Orientation non fournie par le MCU : -1 en premiere case, convention ROS.

    La valeur 0, publiee jusqu'ici, affirmait au contraire une orientation valide.
    """
    return [-1.0, 0.0, 0.0,
            0.0, 0.0, 0.0,
            0.0, 0.0, 0.0]


def covariance_gyro(variance: float = VARIANCE_GYRO) -> list[float]:
    return diagonale(variance, variance, variance)


def covariance_accel(variance: float = VARIANCE_ACCEL) -> list[float]:
    return diagonale(variance, variance, variance)
