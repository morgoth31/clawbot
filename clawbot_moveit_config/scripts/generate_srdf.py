#!/usr/bin/env python3
"""Genere config/clawbot_x3plus.srdf depuis urdf/clawbot_x3plus.urdf.

    python3 clawbot_moveit_config/scripts/generate_srdf.py

Le SRDF n'est pas saisi a la main : les chaines et la matrice de collisions autorisees
(ACM) se deduisent de l'arbre cinematique. Relancer ce script apres toute modification de
l'URDF, puis comparer le resultat a la version versionnee.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
DEFAULT_URDF = os.path.join(PACKAGE, '..', 'urdf', 'clawbot_x3plus.urdf')
DEFAULT_SRDF = os.path.join(PACKAGE, 'config', 'clawbot_x3plus.srdf')

ARM_CHAIN = [f'arm_joint{i}' for i in range(1, 6)]
ARM_LINKS = [f'arm_link{i}' for i in range(5)]
GRIP_JOINT = 'grip_joint'

# P13 : les poses nommees ne sont plus ecrites ici. Elles viennent de
# `config/arm_poses.yaml`, la liste validee par l'operateur (avec nom et date de
# validation). MoveIt en fait des `group_state` — c'est lui qui les sert — mais la
# source reste le YAML, seul endroit ou la validation est tracee.
POSES_YAML = os.path.join(PACKAGE, '..', 'config', 'arm_poses.yaml')
RACINE_DEPOT = os.path.abspath(os.path.join(PACKAGE, '..'))


def charger_poses(chemin=POSES_YAML):
    """Poses validees (nom -> 6 positions en radians) et butees de pince."""
    import sys

    import yaml

    # Une seule conversion servo -> radians dans le depot : celle du controleur.
    sys.path.insert(0, os.path.join(RACINE_DEPOT, 'clawbot_arm_controller'))
    from clawbot_arm_controller.servo_mapping import default_arm_specs, default_gripper_spec

    with open(chemin, encoding='utf-8') as handle:
        document = yaml.safe_load(handle) or {}
    specs = default_arm_specs() + [default_gripper_spec()]
    poses = {}
    for nom, entree in (document.get('poses') or {}).items():
        if not entree.get('validated_by') or not entree.get('validated_at'):
            raise SystemExit(f'{nom} : pose sans validated_by/validated_at, elle n\'est pas '
                             'commandable et ne doit pas entrer dans le SRDF')
        positions = [spec.to_joint_rad(float(deg))
                     for spec, deg in zip(specs, entree['servo_deg'])]
        poses[nom] = positions[:5]
    pince = document.get('pince') or {}
    pince_rad = {
        'open': default_gripper_spec().to_joint_rad(float(pince['ouvert']['servo_deg'])),
        'closed': default_gripper_spec().to_joint_rad(float(pince['ferme']['servo_deg'])),
    }
    return poses, pince_rad


def parse_joints(urdf_text):
    joints = re.findall(
        r'<joint name="([^"]+)"[^>]*type="([^"]+)"[^>]*>(.*?)</joint>', urdf_text, re.S)
    edges = []
    for name, jtype, body in joints:
        parent = re.search(r'<parent link="([^"]+)"', body).group(1)
        child = re.search(r'<child link="([^"]+)"', body).group(1)
        edges.append((name, jtype, parent, child))
    return edges


def collision_pairs(edges):
    """Adjacence 1 partout, adjacence 2 dans la chaine du bras."""
    parent_of = {child: parent for _, _, parent, child in edges}
    arm_parents = {'base_link', *ARM_LINKS[:-1]}
    pairs = set()
    for _, _, parent, child in edges:
        pairs.add(tuple(sorted((parent, child))))
        if parent in arm_parents or parent.startswith(('rlink', 'llink')):
            grand = parent_of.get(parent)
            if grand is not None:
                pairs.add(tuple(sorted((grand, child))))
    return pairs


def build_poses_block(poses, pince_rad):
    """Lignes `<group_state>` : poses validees du bras, puis les deux butees de pince."""
    lignes = []
    for nom, positions in poses.items():
        lignes.append(f'  <group_state name="{nom}" group="arm">')
        for joint, valeur in zip(ARM_CHAIN, positions):
            lignes.append(f'    <joint name="{joint}" value="{valeur:.6f}"/>')
        lignes += ['  </group_state>', '']
    lignes += [
        '  <group_state name="open" group="gripper">',
        f'    <joint name="{GRIP_JOINT}" value="{pince_rad["open"]:.6f}"/>',
        '  </group_state>',
        '',
        '  <group_state name="closed" group="gripper">',
        f'    <joint name="{GRIP_JOINT}" value="{pince_rad["closed"]:.6f}"/>',
        '  </group_state>',
        '',
    ]
    return lignes


def build_srdf(edges):
    lignes_poses, pince_rad = charger_poses()
    if not lignes_poses:
        raise SystemExit('aucune pose validee dans config/arm_poses.yaml : le SRDF serait vide')
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<robot name="clawbot_x3plus">',
        '  <!-- Genere par clawbot_moveit_config/scripts/generate_srdf.py depuis',
        '       urdf/clawbot_x3plus.urdf et config/arm_poses.yaml.',
        '       Ne pas editer a la main : relancer le script. -->',
        '',
        '  <group name="arm">',
        '    <chain base_link="base_link" tip_link="arm_link5"/>',
        '  </group>',
        '',
        '  <group name="gripper">',
        f'    <joint name="{GRIP_JOINT}"/>',
        '  </group>',
        '',
        '  <end_effector name="gripper" parent_link="arm_link5" group="gripper" '
        'parent_group="arm"/>',
        '',
    ]
    lines += build_poses_block(lignes_poses, pince_rad)
    for link1, link2 in sorted(collision_pairs(edges)):
        lines.append(
            f'  <disable_collisions link1="{link1}" link2="{link2}" reason="Adjacent"/>')
    lines += ['', '</robot>', '']
    return '\n'.join(lines)


def remplacer_poses(srdf_text, poses, pince_rad):
    """Reecrit uniquement les `<group_state>` d'un SRDF existant.

    La matrice de collisions autorisees n'est pas touchee : regenerer tout le fichier
    depuis l'URDF changerait aussi des paires `disable_collisions` heritees d'une
    version anterieure du modele, ce qui n'a rien a voir avec les poses.
    """
    lignes = srdf_text.splitlines()
    debut = next((i for i, ligne in enumerate(lignes)
                  if ligne.strip().startswith('<end_effector')), None)
    if debut is None:
        raise SystemExit('SRDF sans <end_effector> : structure inattendue')
    debut += 1
    while debut < len(lignes) and not lignes[debut].strip():
        debut += 1
    fin = next((i for i, ligne in enumerate(lignes)
                if i > debut and (ligne.strip().startswith('<!--')
                                  or ligne.strip().startswith('<disable_collisions'))), None)
    if fin is None:
        raise SystemExit('SRDF sans section de collisions : structure inattendue')
    return '\n'.join(lignes[:debut] + build_poses_block(poses, pince_rad) + lignes[fin:]) + '\n'


def main(argv=None):
    import sys

    poses_only = '--poses-only' in (argv if argv is not None else sys.argv[1:])
    poses, pince_rad = charger_poses()
    if poses_only:
        with open(DEFAULT_SRDF, encoding='utf-8') as handle:
            actuel = handle.read()
        with open(DEFAULT_SRDF, 'w', encoding='utf-8') as handle:
            handle.write(remplacer_poses(actuel, poses, pince_rad))
        print(f'{DEFAULT_SRDF} : {len(poses)} pose(s) validee(s) ecrite(s), '
              'collisions inchangees')
        return 0

    urdf_path = os.environ.get('CLAWBOT_URDF', DEFAULT_URDF)
    with open(urdf_path, encoding='utf-8') as handle:
        edges = parse_joints(handle.read())
    srdf = build_srdf(edges)
    with open(DEFAULT_SRDF, 'w', encoding='utf-8') as handle:
        handle.write(srdf)
    print(f'{DEFAULT_SRDF} ecrit, {len(collision_pairs(edges))} paires desactivees')
    return 0


if __name__ == '__main__':
    main()
