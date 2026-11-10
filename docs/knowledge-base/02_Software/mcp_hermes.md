---
title: "Serveur MCP du pont — câblage ROS 2 et connexion à Hermes"
date: "2026-11-11T00:18:00+01:00"
author: "Hermes Agent"
tags: [software, mcp, hermes, pont, ros2, outils, autonomie]
status: validé
---

# Serveur MCP du pont — câblage ROS 2 et connexion à Hermes

Le pont `ros2_llm_bridge` expose un serveur MCP de 22 outils. Ceux qui touchent ROS 2 refusaient en
`MCP-E-PREREQ` (« couche non câblée ») : Hermes voyait les outils mais n'obtenait aucune donnée.
La couche basse est désormais câblée sur des mesures réelles, et le serveur est enregistré dans
Hermes en transport stdio.

Retour à l'[[index]] ; inventaire : [[inventaire_materiel]] ; spécification : [[llm2ros_mcp_specification]].

## 1. Ce qui a été câblé

| Outil | Source de la donnée | État |
|---|---|---|
| `graph_snapshot` | `ros2 node list`, `ros2 topic list -t` | câblé — 15 nœuds, 38 topics mesurés |
| `topic_stats` | `ros2 topic info` + `ros2 topic hz --window 20` | câblé — `/scan` 10,082 Hz mesuré |
| `tf_snapshot` | échantillonnage de `/tf_static` et `/tf` | câblé — arêtes `parent/frame_id` → `child_frame_id` |
| `param_get`, `param_list` | `ros2 param get/list` sur nœuds vivants | câblé — `angular_limit = 5.0` lu sur `/driver_node` |
| `goal_list` | `ros2 action list -t` | câblé — 4 actions du domaine |
| `goal_send` | `ros2 action send_goal` vers les contrôleurs du bras | câblé, borné (voir §3) |
| `safety_stop` | `ros2 topic pub /cmd_vel` vitesse nulle ×3, puis verrou | câblé, avec limite explicite (voir §3) |
| `diagnostics`, `logs_tail`, `audit_tail`, `resources_snapshot`, `capabilities` | rapport de santé, journal d'audit, `/proc`, sysfs | déjà fonctionnels |
| `param_set`, `param_restore`, `goal_cancel`, `patch_propose`, `test_run` | arbitre d'actionneurs | **toujours en `MCP-E-PREREQ`** (non câblés) |

Traduction des erreurs : `RosUnavailable → MCP-E-PREREQ`, `RosInvalid → MCP-E-ARG`,
`RosTimeout → MCP-E-TIMEOUT`. Aucun outil n'invente de valeur : sans réponse de ROS 2, il refuse
avec un code et un `detail`.

## 2. Connexion à Hermes

Le serveur tourne en **stdio** : Hermes lance `python3 -m bridge_mcp.stdio` à la demande, aucun port
n'est exposé. Le mode HTTP streaming (`127.0.0.1:8090`, jeton porteur, garde anti-rebinding) reste
disponible pour un autre client.

```text
$ hermes mcp list
Name      Transport                        Tools    Status
clawbot   /usr/bin/python3 -m bridg...     all      ✓ enabled
```

```text
$ hermes mcp test clawbot
  → 22 outils listés (graph_snapshot, topic_stats, tf_snapshot, goal_send, safety_stop, …)
```

Vérification d'un **appel** réel, client MCP officiel, transport stdio :

```text
serveur : clawbot-bridge 0.1.0
outils  : 22
appel   : graph_snapshot  -> 15 nœuds, 38 topics
appel   : topic_stats /scan -> 10.082 Hz, 1 éditeur
```

Les outils sont chargés au démarrage d'une session Hermes : dans une session déjà ouverte, il faut
redémarrer Hermes ou exécuter `/reload-mcp`. C'est pourquoi la session qui a fait ce câblage ne voit
pas encore `mcp_clawbot_*` dans sa propre liste d'outils.

## 3. Garde-fous conservés

| Garde-fou | Application |
|---|---|
| Actions autorisées | `limits.py` : uniquement les deux contrôleurs `follow_joint_trajectory` |
| Articulations | `ros_layer.ACTION_SPECS` impose la liste exacte (`arm_joint1..5` ou `grip_joint`) |
| Bornes | bras `[-1,5708 ; 3,14159]` rad, pince `[-1,54 ; 0]` rad, durée `[0,5 ; 10]` s |
| Mutations | `param_set`, `param_restore`, `goal_cancel`, `patch_propose`, `test_run` exigent un incident ouvert |
| `goal_send` | fonctionne avec ou sans incident, mais chaque appel est journalisé (`state.record`) |
| `safety_stop` | publie la vitesse nulle et verrouille `stop_latched` ; **ne coupe pas le bras** — l'arrêt physique reste requis |

## 4. Limites

- `topic_stats` mesure sur une fenêtre de 2 à 30 s : c'est une cadence observée à l'instant, pas une
  garantie de stabilité.
- `tf_snapshot` lit les trames pendant 3 s par topic : une arête publiée moins souvent peut manquer.
- `goal_list` ne liste pas les objectifs en cours (pas d'introspection d'action en Humble).
- `safety_stop` n'arrête ni le bras ni les servos : aucun couple/arrêt matériel n'est exposé.
- Le serveur ne survit pas à la fermeture de la session Hermes en mode stdio : c'est le client qui le
  possède. Pour un accès permanent, utiliser le mode HTTP et une unité systemd (non déployée ici).

## 5. Voir aussi

- Inventaire matériel : [[inventaire_materiel]]
- Spécification MCP : [[llm2ros_mcp_specification]], [[llm2ros_mcp_test_plan]]
- Pont LLM → ROS 2 : [[llm2ros_bridge]], [[llm2ros_bridge_architecture]]
- Manipulation exposée par `goal_send` : [[manipulation_moveit]]
