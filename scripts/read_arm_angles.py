#!/usr/bin/env python3
"""Lit les angles reels des six servos du bras sur la carte Rosmaster.

Le port serie du MCU est exclusif : ce script exige que `ros2-driver-node.service` soit
arrete, sinon l'ouverture de /dev/myserial echoue (ou pire, les deux se disputent les
trames). Procedure complete :

    sudo systemctl stop ros2-driver-node.service
    python3 scripts/read_arm_angles.py
    sudo systemctl start ros2-driver-node.service
    ros2 topic hz /voltage   # doit remonter a ~10 Hz

Aucune consigne n'est envoyee : la fonction appelee ne fait que demander les angles.
"""

import argparse
import subprocess
import sys
import time

ROSMASTER_PATHS = [
    '/home/jetson/yahboomcar_ros2_ws/software/py_install_V3.3.1',
    '/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/src/yahboomcar_bringup',
]


def main() -> int:
    parser = argparse.ArgumentParser(description='Lecture des angles servo du bras')
    parser.add_argument('--port', default='/dev/myserial')
    parser.add_argument('--lectures', type=int, default=3)
    parser.add_argument('--pause', type=float, default=0.3)
    parser.add_argument('--force', action='store_true',
                        help='lire meme si le pilote tourne (deconseille : il perd des trames)')
    args = parser.parse_args()

    # Deux processus qui lisent /dev/myserial se volent les octets : le pilote leve
    # « multiple access on port? » et redemarre. On refuse par defaut.
    if not args.force:
        actif = subprocess.run(['systemctl', 'is-active', '--quiet',
                                'ros2-driver-node.service']).returncode == 0
        if actif:
            print('REFUS : ros2-driver-node.service tourne encore et lit le port serie.\n'
                  '        sudo systemctl stop ros2-driver-node.service  (puis relancer)')
            return 2

    for path in ROSMASTER_PATHS:
        sys.path.insert(0, path)
    try:
        from Rosmaster_Lib import Rosmaster
    except ImportError as exc:
        print(f'ECHEC : Rosmaster_Lib introuvable ({exc})')
        return 1

    try:
        car = Rosmaster(com=args.port)
    except Exception as exc:  # port occupe, absent, droits
        print(f'ECHEC : ouverture de {args.port} impossible : {exc}')
        print('        le pilote tourne-t-il encore ? '
              'sudo systemctl stop ros2-driver-node.service')
        return 1

    # Sans ces deux appels, aucun callback n'est traite : get_uart_servo_angle_array()
    # et get_battery_voltage() renvoient -1 / 0.0 alors que la liaison est bonne.
    # C'est exactement ce que fait Mcnamu_driver_X3 (set_car_type(1) puis
    # create_receive_threading()).
    car.set_car_type(1)
    car.create_receive_threading()
    time.sleep(1.0)
    tension = car.get_battery_voltage()
    version = car.get_version()
    print(f'liaison serie : version={version} tension={tension:.2f} V '
          f'({"OK" if version != -1 else "PAS DE REPONSE"})')

    # Pas de fermeture explicite du port : le thread de lecture de Rosmaster_Lib tourne
    # encore et leve une exception quand le descripteur disparait. Le port est rendu par
    # le systeme a la sortie du processus.
    for index in range(args.lectures):
        angles = car.get_uart_servo_angle_array()
        print(f'lecture {index + 1} : {angles}   (servos 1 a 6, degres ; -1 = pas de reponse)')
        time.sleep(args.pause)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
