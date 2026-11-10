#!/usr/bin/env python3
"""Ecrit les zeros (et les signes) de la conversion servo -> articulation du bras.

La conversion utilisee par `clawbot_arm_controller` est :

    angle_servo_deg = zero_deg + scale_deg_per_rad * q      (q en radians)

`zero_deg` est l'angle servo qui correspond a q = 0 dans le modele URDF, `scale` vaut
57,2958 (180/pi) pour un axe positif et -57,2958 pour un axe inverse. Tant que ces
valeurs sont la convention par defaut (90, +57,2958), le modele peut placer le bras
ailleurs que la realite : MoveIt declare alors valides des configurations qui touchent.

    # exemple : l'axe 2 est vertical a 95° et tourne dans le sens negatif
    python3 scripts/set_arm_zeros.py --zeros "90,95,90,90,90" --signs "+, -, +, +, +"

Puis resynchroniser la pose et redemarrer le controleur :

    sudo systemctl stop ros2-driver-node
    python3 scripts/sync_arm_pose.py
    sudo systemctl start ros2-driver-node
    sudo systemctl restart clawbot-arm-controller

Procedure de mesure des zeros : page `etalonnage_bras` de la base de connaissances.
"""

import argparse
import math
import re

DEFAULT_CONFIG = '/home/jetson/clawbot/clawbot_arm_controller/config/arm_controller.yaml'
RAD_TO_DEG = 180.0 / math.pi


def _liste(texte):
    return [float(v) for v in re.findall(r'-?\d+\.?\d*', texte)]


def main(argv=None):
    parser = argparse.ArgumentParser(description='Zeros et signes de la conversion servo')
    parser.add_argument('--config', default=DEFAULT_CONFIG)
    parser.add_argument('--zeros', required=True,
                        help='angles servo (deg) correspondant a q=0, pour arm_joint1..5')
    parser.add_argument('--signs', default='+,+,+,+,+',
                        help='signe de chaque axe : + ou -, separes par des virgules')
    parser.add_argument('--grip-zero', type=float, default=180.0,
                        help='angle servo de la pince a q=0 (fermee)')
    parser.add_argument('--grip-sign', default='+', choices=['+', '-'])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)

    zeros = _liste(args.zeros)
    signes = [s.strip() for s in args.signs.split(',') if s.strip()]
    if len(zeros) != 5 or len(signes) != 5:
        raise SystemExit('ECHEC : il faut 5 zeros et 5 signes')
    if any(s not in ('+', '-') for s in signes):
        raise SystemExit('ECHEC : les signes valides sont + et -')
    if any(not 0.0 <= z <= 270.0 for z in zeros):
        raise SystemExit('ECHEC : un zero hors de [0, 270] deg n a pas de sens')

    with open(args.config, encoding='utf-8') as handle:
        contenu = handle.read()

    def remplacer(cle, valeur):
        nonlocal contenu
        motif = rf'^(\s*){cle}:\s*\[[^\]]*\]'
        if not re.search(motif, contenu, re.M):
            raise SystemExit(f'ECHEC : {cle} absent de {args.config}')
        contenu = re.sub(motif, lambda m: f'{m.group(1)}{cle}: {valeur}', contenu,
                         count=1, flags=re.M)

    echelles = [('-' if s == '-' else '') + f'{RAD_TO_DEG:.8f}' for s in signes]
    remplacer('arm_zero_deg', '[' + ', '.join(f'{z:.1f}' for z in zeros) + ']')
    remplacer('arm_scale_deg_per_rad', '[' + ', '.join(echelles) + ']')
    remplacer('grip_zero_deg', f'[{args.grip_zero:.1f}]')
    remplacer('grip_scale_deg_per_rad',
              f'[{"-" if args.grip_sign == "-" else ""}{RAD_TO_DEG:.8f}]')

    print('zeros (deg)   : ' + ', '.join(f'{z:.1f}' for z in zeros))
    print('signes        : ' + ', '.join(signes))
    print('pince         : zero ' + f'{args.grip_zero:.1f}' + ', signe ' + args.grip_sign)
    print('exemple : consigne servo 100° -> q = '
          + ', '.join(f'{(100.0 - z) / (RAD_TO_DEG if s == "+" else -RAD_TO_DEG):+.3f}'
                      for z, s in zip(zeros, signes)) + ' rad')

    if args.dry_run:
        print('mode --dry-run : fichier non modifie')
        return 0
    with open(args.config, 'w', encoding='utf-8') as handle:
        handle.write(contenu)
    print(f'{args.config} mis a jour')
    print('resynchroniser la pose (sync_arm_pose.py) puis redemarrer clawbot-arm-controller')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
