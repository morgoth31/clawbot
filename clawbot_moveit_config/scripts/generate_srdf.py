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


def build_srdf(edges):
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<robot name="clawbot_x3plus">',
        '  <!-- Genere par clawbot_moveit_config/scripts/generate_srdf.py depuis',
        '       urdf/clawbot_x3plus.urdf. Ne pas editer a la main : relancer le script. -->',
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
        '  <group_state name="home" group="arm">',
    ]
    for joint in ARM_CHAIN:
        lines.append(f'    <joint name="{joint}" value="0"/>')
    lines += [
        '  </group_state>',
        '',
        '  <group_state name="ready" group="arm">',
        '    <joint name="arm_joint1" value="0"/>',
        '    <joint name="arm_joint2" value="0.5"/>',
        '    <joint name="arm_joint3" value="0.5"/>',
        '    <joint name="arm_joint4" value="0"/>',
        '    <joint name="arm_joint5" value="0"/>',
        '  </group_state>',
        '',
        '  <group_state name="open" group="gripper">',
        f'    <joint name="{GRIP_JOINT}" value="-1.54"/>',
        '  </group_state>',
        '',
        '  <group_state name="closed" group="gripper">',
        f'    <joint name="{GRIP_JOINT}" value="0"/>',
        '  </group_state>',
        '',
        '  <!-- Collisions ignorees : adjacence 1 partout, adjacence 2 dans le bras. -->',
    ]
    for link1, link2 in sorted(collision_pairs(edges)):
        lines.append(
            f'  <disable_collisions link1="{link1}" link2="{link2}" reason="Adjacent"/>')
    lines += ['', '</robot>', '']
    return '\n'.join(lines)


def main():
    urdf_path = os.environ.get('CLAWBOT_URDF', DEFAULT_URDF)
    with open(urdf_path, encoding='utf-8') as handle:
        edges = parse_joints(handle.read())
    srdf = build_srdf(edges)
    with open(DEFAULT_SRDF, 'w', encoding='utf-8') as handle:
        handle.write(srdf)
    print(f'{DEFAULT_SRDF} ecrit, {len(collision_pairs(edges))} paires desactivees')


if __name__ == '__main__':
    main()
