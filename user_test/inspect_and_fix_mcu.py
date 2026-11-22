#!/usr/bin/env python3
"""
Diagnostic et configuration EEPROM pour la carte Yahboom Rosmaster X3 Plus.
Prérequis : ros2-driver-node.service doit être arrêté avant d'ouvrir /dev/myserial.
"""

import argparse
import sys
import time
from Rosmaster_Lib import Rosmaster

SERIAL_PORT = "/dev/myserial"
CAR_TYPE_NAMES = {
    1: "X3 (Mecanum standard - moteurs 370)",
    2: "X3 Plus (Mecanum Max - moteurs 520)",
    4: "R2 (Ackermann)",
    5: "X1 (Différentiel)",
}


def connect_mcu(port: str, init_car_type: int = 2) -> Rosmaster:
    print(f"[INFO] Ouverture de {port} (car_type d'instance={init_car_type})...")
    try:
        bot = Rosmaster(car_type=init_car_type, com=port, debug=False)
    except Exception as exc:
        print(f"[ERREUR] Impossible d'ouvrir {port} : {exc}")
        print("Vérifiez que ros2-driver-node.service est bien arrêté.")
        sys.exit(1)

    # Indispensable : sans ce thread interne, les getters renvoient -1
    bot.create_receive_threading()
    time.sleep(0.25)
    return bot


def read_mcu_state(bot: Rosmaster) -> dict:
    # Activation temporaire du rapport automatique pour rafraîchir les encodeurs/vitesses
    bot.set_auto_report_state(True, forever=False)
    time.sleep(0.15)

    version = bot.get_version()
    time.sleep(0.05)

    car_type = bot.get_car_type_from_machine()
    time.sleep(0.05)

    motion_pid = bot.get_motion_pid()
    time.sleep(0.05)

    voltage = bot.get_battery_voltage()
    encoders = bot.get_motor_encoder()
    vx, vy, vz = bot.get_motion_data()

    return {
        "version": version,
        "car_type": car_type,
        "motion_pid": motion_pid,
        "voltage": voltage,
        "encoders": encoders,
        "motion_data": (vx, vy, vz),
    }


def print_state(state: dict) -> None:
    ct = state["car_type"]
    ct_label = CAR_TYPE_NAMES.get(ct, f"Inconnu ({ct})")
    print("\n=== ÉTAT ACTUEL DU MCU STM32 ===")
    print(f"  Firmware version : {state['version']}")
    print(f"  Tension batterie : {state['voltage']:.2f} V")
    print(f"  car_type EEPROM  : {ct} -> {ct_label}")
    print(f"  PID vitesse (Kp, Ki, Kd) : {state['motion_pid']}")
    print(f"  Encodeurs [M1, M2, M3, M4] : {state['encoders']}")
    print(f"  Vitesse brute (vx, vy, wz) : {state['motion_data']}")
    print("================================\n")


def apply_x3_plus_type(bot: Rosmaster) -> None:
    print("[ACTION] Écriture de car_type = 2 (X3 Plus) avec sauvegarde flash...")
    # set_car_type(2) configure la cinématique courante
    bot.set_car_type(2)
    time.sleep(0.15)
    # Selon la révision de Rosmaster_Lib, la persistance flash se fait via
    # l'octet forever=True ou via l'enregistrement d'état :
    try:
        bot.set_car_type(2)
    except TypeError:
        pass
    time.sleep(0.2)

    new_ct = bot.get_car_type_from_machine()
    print(f"[VÉRIFICATION] Nouveau car_type relu depuis la carte : {new_ct}")
    if new_ct == 2:
        print("[OK] Le MCU est maintenant configuré en X3 Plus (car_type=2).")
    else:
        print(
            "[ATTENTION] get_car_type_from_machine() renvoie encore "
            f"{new_ct}. Il faudra forcer bot.set_car_type(2) dans l'init de Mcnamu_driver_X3.py."
        )


def interactive_wheel_test(bot: Rosmaster, duration_s: int = 10) -> None:
    print(f"\n[TEST ROUES] Tournez chaque roue à la main vers l'AVANT pendant {duration_s} s.")
    print("Convention attendue : les compteurs doivent augmenter (+) quand la roue tourne vers l'avant.")
    print("Ordre : [M1=Avant-Gauche, M2=Arrière-Gauche, M3=Avant-Droite, M4=Arrière-Droite]\n")

    bot.set_auto_report_state(True, forever=False)
    time.sleep(0.1)
    baseline = list(bot.get_motor_encoder())
    print(f"Base initiale : {baseline}")

    t0 = time.monotonic()
    try:
        while (time.monotonic() - t0) < duration_s:
            enc = bot.get_motor_encoder()
            deltas = [enc[i] - baseline[i] for i in range(4)]
            vx, vy, wz = bot.get_motion_data()
            print(
                f"\rΔEncodeurs: M1={deltas[0]:+6d} | M2={deltas[1]:+6d} | "
                f"M3={deltas[2]:+6d} | M4={deltas[3]:+6d}  ||  vx={vx:+.3f} m/s",
                end="",
                flush=True,
            )
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    print("\n[FIN TEST ROUES]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic EEPROM Rosmaster X3 Plus")
    parser.add_argument("--port", default=SERIAL_PORT, help="Port série du MCU")
    parser.add_argument(
        "--fix-cartype",
        action="store_true",
        help="Force car_type=2 (X3 Plus) sur le MCU",
    )
    parser.add_argument(
        "--set-pid",
         nargs=3,
        type=float,
        metavar=("KP", "KI", "KD"),
        help="Applique un nouveau PID de vitesse (ex: --set-pid 0.5 0.1 0.3) en RAM/EEPROM",
    )
    parser.add_argument(
        "--test-wheels",
        action="store_true",
        help="Affiche les deltas des 4 encodeurs en temps réel pendant 10 s",
    )
    args = parser.parse_args()

    bot = connect_mcu(args.port, init_car_type=2)
    state = read_mcu_state(bot)
    print_state(state)

    if args.fix_cartype:
        apply_x3_plus_type(bot)

    if args.set_pid:
        kp, ki, kd = args.set_pid
        print(f"[ACTION] Application du PID : Kp={kp}, Ki={ki}, Kd={kd}...")
        bot.set_pid_param(kp, ki, kd, forever=True)
        time.sleep(0.2)
        print(f"[VÉRIFICATION] PID relu : {bot.get_motion_pid()}")

    if args.test_wheels:
        interactive_wheel_test(bot, duration_s=15)

    # Sécurité : consigne nulle avant de quitter
    bot.set_car_motion(0.0, 0.0, 0.0)
    del bot


if __name__ == "__main__":
    main()
