---
type: Known Issue
title: "MoveIt2 Manquant -- Planification Bras 5-DOF"
description: Le bras 5-DOF n'a pas de planification de trajectoire. Controle manuel par angles uniquement.
status: draft
tags: [todo, moveit2, arm, planning]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:35:00Z
sources:
  - id: work-state
    resource: file:///home/jetson/clawbot/WORK_STATE.md
    title: WORK_STATE.md
    author: human:jetson
    last_modified: 2026-03-02
  - id: codebase-map
    resource: file:///home/jetson/clawbot/CODEBASE_MAP.md
    title: CODEBASE_MAP.md
    author: human:jetson
    last_modified: 2026-03-06
---

# MoveIt2 Manquant

## Etat Actuel
- Le bras est controle uniquement par angles absolus (ControlServo, ControlArm)
- Pas de planification de trajectoire, pas d'IK, pas d'evitement d'obstacles
- Le plugin ros2_control (C++) est compile mais non integre
- Config MoveIt2 dans `/home/jetson/clawbot/moveit/` (incomplet)

## Ce qui Manque
1. **SRDF**: Semantic Robot Description Format pour MoveIt2
2. **kinematics.yaml**: configuration du solver IK
3. **move_group**: launch file pour le noeud MoveIt2
4. **ros2_control plugin**: integration complete du hardware_interface C++

## Blocker
Le plugin ros2_control (`clawbot_hardware_interface`) est compile mais:
- Non integre avec MoveIt2
- Conflit serial non resoluplus
- Necessite le merge des drivers d'abord

## Priorite
Moyenne (1-4h pour config MoveIt2 Setup Assistant, >4h pour integration complete)