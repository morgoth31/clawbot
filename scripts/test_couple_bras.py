"""Test direct du couple et d'un petit pas servo, hors de la pile ROS.

Sert à séparer deux causes qui se ressemblent : « la pile ROS n'envoie pas » et « le MCU reçoit mais
les servos n'exécutent pas ». Le script parle à la carte avec `Rosmaster_Lib`, sans passer par le
pilote (qui doit donc être arrêté : le port série est exclusif).

Ce qu'il fait, dans cet ordre :
  1. ouvre la liaison et lit la tension (preuve que la carte répond) ;
  2. envoie explicitement `set_uart_servo_torque(1)` — la commande que le pilote envoie à son
     démarrage, mais dont personne ne vérifie le résultat ;
  3. relit les angles ;
  4. envoie **un** petit pas sur un servo (5° par défaut) et relit ;
  5. laisse le bras dans cette position : c'est à l'opérateur de dire s'il a bougé.

    sudo systemctl stop ros2-driver-node.service
    python3 scripts/test_couple_bras.py --servo 4 --pas 5
    sudo systemctl start ros2-driver-node.service
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

ROSMASTER_PATHS = [
    "/home/jetson/yahboomcar_ros2_ws/software/py_install_V3.3.1",
    "/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/src/yahboomcar_bringup",
]


def main() -> int:
    analyseur = argparse.ArgumentParser(description="Couple + petit pas servo, hors pile ROS")
    analyseur.add_argument("--port", default="/dev/myserial")
    analyseur.add_argument("--servo", type=int, default=4, choices=[1, 2, 3, 4, 5, 6])
    analyseur.add_argument("--pas", type=float, default=5.0, help="amplitude du pas, en degres")
    analyseur.add_argument("--force", action="store_true")
    arguments = analyseur.parse_known_args()[0]

    if not arguments.force:
        actif = subprocess.run(["systemctl", "is-active", "--quiet",
                                "ros2-driver-node.service"]).returncode == 0
        if actif:
            print("REFUS : ros2-driver-node.service lit /dev/myserial. "
                  "sudo systemctl stop ros2-driver-node.service")
            return 2

    for chemin in ROSMASTER_PATHS:
        sys.path.insert(0, chemin)
    from Rosmaster_Lib import Rosmaster

    carte = Rosmaster(com=arguments.port)
    carte.set_car_type(1)
    carte.create_receive_threading()
    time.sleep(1.0)

    tension = carte.get_battery_voltage()
    version = carte.get_version()
    print(f"carte : version={version} tension={tension:.2f} V "
          f"({'repond' if version != -1 else 'MUETTE'})")
    if version == -1:
        return 1

    avant = carte.get_uart_servo_angle_array()
    print(f"angles (registre du MCU) avant : {avant}")

    print("envoi de set_uart_servo_torque(1) ...")
    carte.set_uart_servo_torque(1)
    time.sleep(0.5)

    index = arguments.servo - 1
    cible = int(round(avant[index] + arguments.pas))
    print(f"pas : servo {arguments.servo} {avant[index]} -> {cible} degres")
    carte.set_uart_servo_angle(arguments.servo, cible)
    time.sleep(1.5)

    apres = carte.get_uart_servo_angle_array()
    print(f"angles (registre du MCU) apres : {apres}")
    print("\nA l'operateur : le bras a-t-il bouge de quelques degres ?")
    print("  - oui  -> la chaine servo fonctionne, le defaut est dans la pile ROS")
    print("  - non  -> le MCU enregistre mais les servos n'executent pas "
          "(couple refuse, servo debranche, ou mode different)")
    # pas de fermeture explicite : le thread de lecture tourne encore
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
