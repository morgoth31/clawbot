#!/usr/bin/env python3
"""Releve la pose reelle du bras et l'ecrit dans la configuration du controleur.

`clawbot_arm_controller` ne peut pas lire la position du bras quand le pilote tourne (port
serie exclusif). Sa configuration porte donc un instantane `initial_positions` : ce script
le rafraichit, ainsi que `initial_grip_position`, a partir des angles lus sur la carte.

    sudo systemctl stop ros2-driver-node.service
    python3 scripts/sync_arm_pose.py
    sudo systemctl restart clawbot-arm-controller.service
    sudo systemctl start ros2-driver-node.service

Les articulations dont le servo renvoie un angle invalide (negatif) sont ajoutees a
`passive_joints` : sans position connue, les commander risquerait un saut. Les valeurs de
conversion (zero, echelle) viennent du meme fichier YAML : une seule source de verite.
"""

import argparse
import re
import subprocess
import sys
import time

ROSMASTER_PATHS = [
    '/home/jetson/yahboomcar_ros2_ws/software/py_install_V3.3.1',
    '/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/src/yahboomcar_bringup',
]
DEFAULT_CONFIG = '/home/jetson/clawbot/clawbot_arm_controller/config/arm_controller.yaml'


def _parse_float_list(text):
    return [float(value) for value in re.findall(r'-?\d+\.?\d*', text)]


def _parse_str_list(text):
    return [item.strip().strip('"\'') for item in text.strip('[]').split(',') if item.strip()]


def read_mapping(config_path):
    """Extrait les parametres de conversion du fichier de configuration du controleur."""
    with open(config_path, encoding='utf-8') as handle:
        content = handle.read()

    def values(key):
        match = re.search(rf'^\s*{key}:\s*(\[[^\]]*\])', content, re.M)
        if not match:
            raise SystemExit(f'ECHEC : {key} absent de {config_path}')
        return match.group(1)

    mapping = {
        'arm_joints': _parse_str_list(values('arm_joints')),
        'arm_servo_ids': [int(v) for v in _parse_float_list(values('arm_servo_ids'))],
        'arm_zero_deg': _parse_float_list(values('arm_zero_deg')),
        'arm_scale_deg_per_rad': _parse_float_list(values('arm_scale_deg_per_rad')),
        'grip_joints': _parse_str_list(values('grip_joints')),
        'grip_servo_ids': [int(v) for v in _parse_float_list(values('grip_servo_ids'))],
        'grip_zero_deg': _parse_float_list(values('grip_zero_deg')),
        'grip_scale_deg_per_rad': _parse_float_list(values('grip_scale_deg_per_rad')),
    }
    return mapping, content


def lire_angles(port='/dev/myserial'):
    for path in ROSMASTER_PATHS:
        sys.path.insert(0, path)
    try:
        from Rosmaster_Lib import Rosmaster
    except ImportError as exc:
        raise SystemExit(f'ECHEC : Rosmaster_Lib introuvable ({exc})')
    try:
        car = Rosmaster(com=port)
    except Exception as exc:
        raise SystemExit(
            f'ECHEC : {port} indisponible ({exc}) — arreter ros2-driver-node.service')
    car.set_car_type(1)
    car.create_receive_threading()
    time.sleep(1.0)
    if car.get_version() == -1:
        raise SystemExit('ECHEC : pas de reponse du MCU sur la liaison serie')
    # Pas de fermeture explicite du port : le thread de lecture de Rosmaster_Lib tourne
    # encore et leve une exception quand le descripteur disparait. Le port est rendu par
    # le systeme a la sortie du processus.
    return car.get_uart_servo_angle_array()


def ecrire_pose(config_path, content, positions, grip_position, passifs):
    def bloc(valeurs):
        return '[' + ', '.join(f'{v:.6f}' for v in valeurs) + ']'

    if not re.search(r'^\s*initial_positions:', content, re.M):
        raise SystemExit(f'ECHEC : initial_positions absent de {config_path}')
    content = re.sub(r'^(\s*)initial_positions:\s*\[[^\]]*\]',
                     lambda m: f'{m.group(1)}initial_positions: {bloc(positions)}',
                     content, flags=re.M)
    content = re.sub(r'^(\s*)initial_grip_position:\s*-?\d+\.?\d*',
                     lambda m: f'{m.group(1)}initial_grip_position: {grip_position:.6f}',
                     content, flags=re.M)
    content = re.sub(r'^(\s*)passive_joints:\s*\[[^\]]*\]',
                     lambda m: f'{m.group(1)}passive_joints: '
                               f'[{", ".join(passifs)}]',
                     content, flags=re.M)
    with open(config_path, 'w', encoding='utf-8') as handle:
        handle.write(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Synchonise la pose du bras dans la config')
    parser.add_argument('--config', default=DEFAULT_CONFIG)
    parser.add_argument('--port', default='/dev/myserial')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true',
                        help='lire meme si le pilote tourne (deconseille : il perd des trames)')
    args = parser.parse_args(argv)

    # Deux lecteurs sur /dev/myserial se volent les octets : le pilote leve
    # « multiple access on port? » puis redemarre. On refuse par defaut.
    if not args.force:
        actif = subprocess.run(['systemctl', 'is-active', '--quiet',
                                'ros2-driver-node.service']).returncode == 0
        if actif:
            print('REFUS : ros2-driver-node.service lit encore le port serie.\n'
                  '        sudo systemctl stop ros2-driver-node.service  (puis relancer)')
            return 2

    mapping, content = read_mapping(args.config)
    angles = lire_angles(args.port)
    print(f'angles lus : {angles}')

    par_servo = {servo: angle for servo, angle in zip(range(1, 7), angles)}

    positions = []
    passifs = []
    for joint, servo_id, zero, echelle in zip(mapping['arm_joints'],
                                              mapping['arm_servo_ids'],
                                              mapping['arm_zero_deg'],
                                              mapping['arm_scale_deg_per_rad']):
        angle = par_servo.get(servo_id, -1)
        if angle < 0:
            positions.append(0.0)
            passifs.append(joint)
            print(f'  {joint} : servo {servo_id} sans angle valide ({angle}) '
                  f'-> position 0.0 et articulation declarée passive')
        else:
            positions.append((angle - zero) / echelle)
            print(f'  {joint} : servo {servo_id} a {angle} deg -> {positions[-1]:+.4f} rad')

    grip_servo = mapping['grip_servo_ids'][0]
    grip_angle = par_servo.get(grip_servo, -1)
    if grip_angle < 0:
        grip_position = 0.0
        passifs.append(mapping['grip_joints'][0])
        print(f'  {mapping["grip_joints"][0]} : servo {grip_servo} sans angle valide')
    else:
        grip_position = ((grip_angle - mapping['grip_zero_deg'][0])
                         / mapping['grip_scale_deg_per_rad'][0])
        print(f'  {mapping["grip_joints"][0]} : servo {grip_servo} a {grip_angle} deg '
              f'-> {grip_position:+.4f} rad')

    if args.dry_run:
        print('mode --dry-run : fichier non modifie')
        return 0

    ecrire_pose(args.config, content, positions, grip_position, passifs)
    print(f'{args.config} mis a jour (initial_positions, initial_grip_position, passive_joints)')
    print('redemarrer le controleur : sudo systemctl restart clawbot-arm-controller.service')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
