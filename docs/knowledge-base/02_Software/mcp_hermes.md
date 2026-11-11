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

## 4. Déclencher une prompt Hermes depuis le Système 1

**Réponse courte** : un serveur MCP ne peut pas prendre l'initiative. Le protocole est piloté par
le client : Hermes ouvre l'appel d'outil, le serveur répond. Pour que le robot réveille Hermes,
trois voies existent — deux hors MCP, une dans MCP.

| Voie | Mécanisme | Disponibilité | Coût / latence |
|---|---|---|---|
| `cli` | S1 lance `hermes chat --oneshot --query-file -`, contexte JSON sur stdin | **vérifiée le 2026-11-11** (46,4 s, réponse exploitable) | une session Hermes complète par appel |
| `webhook` | S1 signe un POST HMAC ; la passerelle Hermes crée l'exécution | route `clawbot-incident` créée, passerelle **à redémarrer** pour l'écouter | asynchrone, découplé de toute session |
| `sampling` | le serveur MCP demande une complétion au client | seulement **pendant** un appel d'outil en cours | inadapté à un réveil spontané |

Module : `bridge_mcp/hermes_trigger.py` — `trigger(context, question, transport="cli"|"webhook")`.

### 4.1 Voie `cli` — opérationnelle

```python
from bridge_mcp.hermes_trigger import trigger
reponse = trigger({"incident": {...}, "topics": {"/scan": {"hz": 10.08}}},
                  "Faut-il relancer la caméra du bras ?", transport="cli")
print(reponse["answer"])
```

Essai réel du 2026-11-11 00:25 : contexte incident + graphe + pose du bras, question sur la
caméra rebranchée → réponse en 46,4 s, structurée en diagnostic / action / garde-fou, appuyée sur
les fiches de la base (`[76, 97, 90, 90, 90, 149]`, seuil 114°, `/dev/video0` sans nœud ROS).

Deux pièges mesurés, corrigés dans le module :

- `--source` provoque un `invalid_params` du fournisseur : ne pas le passer.
- l'atteinte de `--max-turns` renvoie un code de sortie non nul **avec** une réponse : seul
  l'absence de texte est un échec.
- le prompt passe par `--query-file -` (stdin), jamais par la ligne de commande : guillemets,
  `$(...)` et backticks du contexte sont préservés verbatim.

### 4.2 Voie `webhook` — configurée, activation en attente

```text
$ hermes webhook subscribe clawbot-incident --events incident --deliver log \
    --prompt "Incident Clawbot (urgence {urgency}) : {question} … {context} …"
  Secret: 2pw65kVM… (propre à la route, pas le secret global)
```

Le module lit l'URL et le **secret de la route** dans `~/.hermes/webhook_subscriptions.json` :
signer avec le secret global donne un 401 silencieux.

Activation — la passerelle a été démarrée avant l'ajout de la plateforme `webhook`, elle ne
l'écoute donc pas encore. Le redémarrage interrompt les sessions Hermes en cours, il est laissé à
l'opérateur :

```bash
hermes gateway restart --yes
curl -s http://127.0.0.1:8644/health     # {"status": "ok"}
```

Tant que ce redémarrage n'est pas fait, `post_webhook` échoue proprement :
`TriggerError: passerelle Hermes injoignable … Connection refused` (vérifié).

### 4.3 Ce que S1 doit envoyer

```json
{"event": "incident", "urgency": "haute", "question": "…",
 "context": {"incident": {"id": "INC-…", "severite": 2}, "topics": {"…": {"hz": 10.0}},
             "bras": {"servos_deg": [76, 97, 90, 90, 90, 149]}, "materiel": {"…": "…"}}}
```

Règle : le contexte est un **relevé mesuré**, jamais une conclusion. Les valeurs inventées sont
refusées par la base (règle de sourçage) et rendent la réponse de S2 inutilisable.

### 4.4 Limites

- Voie `cli` : pas de continuité entre appels ; chaque déclenchement ouvre une session neuve.
- Voie `webhook` : `--deliver log` seulement ; pour pousser la réponse vers un canal, remplacer
  par `--deliver telegram --deliver-chat-id …` et redémarrer la passerelle.
- Aucune voie ne permet à S1 d'**exécuter** une action : S2 propose, S1 décide et agit.

## 5. Limites du serveur MCP

- `topic_stats` mesure sur une fenêtre de 2 à 30 s : c'est une cadence observée à l'instant, pas une
  garantie de stabilité.
- `tf_snapshot` lit les trames pendant 3 s par topic : une arête publiée moins souvent peut manquer.
- `goal_list` ne liste pas les objectifs en cours (pas d'introspection d'action en Humble).
- `safety_stop` n'arrête ni le bras ni les servos : aucun couple/arrêt matériel n'est exposé.
- Le serveur ne survit pas à la fermeture de la session Hermes en mode stdio : c'est le client qui le
  possède. Pour un accès permanent, utiliser le mode HTTP et une unité systemd (non déployée ici).

## 6. Voir aussi

- Inventaire matériel : [[inventaire_materiel]]
- Déclenchement S1 → S2 : §4 de cette page
- Spécification MCP : [[llm2ros_mcp_specification]], [[llm2ros_mcp_test_plan]]
- Pont LLM → ROS 2 : [[llm2ros_bridge]], [[llm2ros_bridge_architecture]]
- Manipulation exposée par `goal_send` : [[manipulation_moveit]]
