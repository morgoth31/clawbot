---
title: "Spécification — pont LLM2ROS en architecture Système 1 / Système 2 (interface MCP)"
date: "2026-11-10T07:35:00+08:00"
author: "Hermes Agent"
tags: [software, ros2, mcp, specification, exigences, systeme-1, systeme-2, architecture]
status: actif
---

# Spécification — pont LLM2ROS Système 1 / Système 2

Étape 1 du projet : spécification formelle des exigences. État constaté du pont actuel :
[[llm2ros_bridge]] ; architecture actuelle : [[llm2ros_bridge_architecture]] ; cahier des charges
fonctionnel déjà établi : [[llm2ros_bridge_specification]].

Ce document définit l'interface MCP, les critères de déclenchement du Système 1 vers le Système 2 et
la structure du contexte transmis. **Aucune valeur d'architecture n'est supposée** : toute valeur
non fournie par l'exploitant figure en §10 comme décision à valider, avec une valeur proposée
explicitement identifiée comme telle.

## 1. Objet, périmètre, frontières

### 1.1 Répartition des rôles

| Système | Nature | Responsabilités | Interdictions |
|---|---|---|---|
| **Système 1 (S1)** | Déterministe, embarqué, temps réel mou | Contrôle, boucles de rétroaction, surveillance, détection de déclencheurs, collecte de contexte, exécution contrôlée des actions validées, journal d'audit | Ne prend aucune décision non modélisée ; n'appelle pas de modèle de langage dans sa boucle de contrôle |
| **Système 2 (S2)** | Raisonnement analytique, hors boucle temps réel | Diagnostic d'événements non modélisés, choix d'une action parmi celles exposées, proposition de refactorisation et de spécification | Ne publie jamais directement sur un topic d'actionneur ; n'exécute pas de code sur le robot ; n'agit que sur sollicitation |

### 1.2 Frontière de commande

```text
        ┌──────────────────────── S1 : robot, domaine ROS 2 = 28 ───────────────────────┐
        │                                                                              │
  ┌─────┴──────┐   ┌──────────────┐   ┌───────────────┐   ┌────────────────┐          │
  │ nœuds      │   │ arbitre      │   │ superviseur   │   │ serveur MCP    │          │
  │ ROS 2      │◄──┤ d'actionneurs├──►│ de sûreté     ├──►│ (JSON-RPC)     │          │
  │ contrôle   │   │ (file unique)│   │ triggers      │   │ tools+resources│          │
  └─────┬──────┘   └──────┬───────┘   └───────┬───────┘   └────────┬───────┘          │
        │                 │                   │                    │                   │
        │ /cmd_vel ...    │ limites, arrêt    │ contexte           │ 127.0.0.1:8090    │
        ▼                 ▼                   ▼                    ▼                   │
   actionneurs      watchdog 1,5 s     journal d'audit      contexte d'incident        │
                                                                  │                    │
        └─────────────────────────────────────────────────────────┼────────────────────┘
                                                                  │  MCP (client natif)
                                                        ┌─────────┴─────────┐
                                                        │  S2 : Hermes      │
                                                        │  raisonnement     │
                                                        └───────────────────┘
```

Invariant de frontière : **aucun chemin d'écriture vers un actionneur ne traverse l'interface MCP**.
Toute action demandée par S2 est une requête déposée dans l'arbitre d'actionneurs de S1, qui applique
bornes, priorités et watchdog. Cette règle découle de [[ERR-2026-11-10-004_execution_de_commande_non_authentifiee]] :
l'exposition actuelle (aucune authentification, écoute `0.0.0.0`) est incompatible avec l'ouverture
d'un canal de raisonnement.

### 1.3 Périmètre de cette étape

Inclus : modèle de déclenchement, contrat MCP, schéma du contexte, invariants de sûreté, exigences
vérifiables et critères d'acceptation.
Exclu : plan de tests (étape 2), squelettes de tests (étape 3), code (étape 4).

## 2. Définitions

| Terme | Définition |
|---|---|
| Incident | Occurrence datée d'une condition de déclenchement, identifiée par `incident_id` |
| Déclencheur (trigger) | Règle déterministe de S1 dont l'évaluation vraie pendant `debounce` crée un incident |
| Contexte | Document JSON décrivant l'état du robot au moment de l'incident (§6) |
| Action S2 | Appel d'outil MCP autorisé pour l'incident courant |
| Politique de reprise | Règle interne de S1 qui résout un incident sans intervention de S2 |
| Cooldown | Intervalle pendant lequel un même déclencheur ne crée pas de nouvel incident |
| S2_MIN | Niveau de sévérité minimal ouvrant le droit à une intervention de S2 |

## 3. Exigences — modèle de déclenchement

### 3.1 Règles de déclenchement

Chaque déclencheur est spécifié par : identifiant, expression de condition, source de mesure,
temporisation (`debounce`), sévérité (1 à 4), classe de contexte, jeux d'outils autorisés, cooldown
et nombre maximal d'incidents par heure.

| ID | Condition | Source | Debounce | Sév. | Outils autorisés |
|---|---|---|---|---|---|
| TRG-01 | Un nœud déclaré critique absent du graphe pendant la fenêtre | `ros2 node list` / graphe DDS | 3 s | 3 | context, `param_*`, `escalate` |
| TRG-02 | Un service ou une action déclarée critique indisponible | introspection du graphe | 2 s | 3 | context, `param_*`, `goal_*`, `escalate` |
| TRG-03 | Topic critique sans données : âge du dernier message > 3 × période déclarée | abonnement S1 | 3 périodes | 2 | context, `param_*`, `escalate` |
| TRG-04 | Cadence mesurée d'un topic critique < 50 % de la cadence nominale pendant 5 s | compteur S1 | 5 s | 2 | context, `param_*`, `escalate` |
| TRG-05 | Incompatibilité QoS confirmée entre un éditeur et un abonné critiques | introspection QoS | immédiat | 2 | context, `param_*`, `escalate` |
| TRG-06 | Transformation TF requise absente ou périmée (> 1 s) | `/tf`, `/tf_static` | 1 s | 3 | context, `escalate` |
| TRG-07 | Température d'une zone au-delà du seuil passif (70 °C) | sysfs thermique | 5 s | 2 | context, `param_*`, `escalate` |
| TRG-08 | Tension batterie sous le seuil bas (valeur en §10, D-06) | `/voltage` | 3 s | 3 | context, `param_*`, `escalate` |
| TRG-09 | Espace libre de la partition racine sous le seuil (valeur en §10, D-07) | `statvfs` | 60 s | 1 | context, `escalate` |
| TRG-10 | Échec d'un objectif d'action (aborted, canceled, rejeté) non prévu par la politique de reprise | client d'action de S1 | immédiat | 3 | context, `goal_*`, `param_*`, `escalate` |
| TRG-11 | Watchdog d'arrêt déclenché deux fois en 30 s sans commande reçue | superviseur | — | 4 | context, `safety_stop`, `escalate` |
| TRG-12 | Échec répété d'un appel d'outil du pont (même outil, 3 échecs en 60 s) | pont | — | 2 | context, `param_*`, `escalate` |
| TRG-13 | Exception non gérée dans un nœud S1 (message hors des classes connues) | `/rosout`, journal | immédiat | 3 | context, `escalate` |
| TRG-14 | Condition non modélisée signalée par S1 lui-même (`unknown_condition` explicite) | superviseur | — | 3 | context, `param_*`, `goal_*`, `escalate` |

### 3.2 Règles de non-déclenchement

| ID | Règle |
|---|---|
| TRG-20 | Un incident déjà ouvert sur le même déclencheur et le même sujet ne crée pas de doublon : il incrémente son compteur et met à jour son contexte |
| TRG-21 | Un déclencheur en cooldown ne crée pas d'incident ; l'événement est journalisé avec le motif `COOLDOWN` |
| TRG-22 | Un incident dont S1 dispose d'une politique de reprise applicable est résolu par S1 sans appel à S2 ; la résolution est journalisée |
| TRG-23 | Un incident de sévérité 4 n'ouvre aucun droit d'action autre que `safety_stop` et `escalate` |
| TRG-24 | Aucun incident n'est créé hors des déclencheurs déclarés : le jeu TRG-01 à TRG-14 est clos. Ajouter un déclencheur exige une modification de spécification et un test de non-régression |

### 3.3 Critères d'acceptation des déclencheurs

| Exigence | Critère d'acceptation |
|---|---|
| TRG-A1 | Chaque déclencheur possède un test qui provoque la condition et vérifie la création d'un incident avec le bon `trigger_id`, la bonne sévérité et le bon contexte |
| TRG-A2 | Chaque déclencheur possède un test qui vérifie l'absence d'incident lorsque la condition est sous le seuil |
| TRG-A3 | TRG-20, TRG-21, TRG-22, TRG-23 et TRG-24 possèdent chacune un test d'invariant |
| TRG-A4 | La latence entre condition vraie et émission de l'incident est inférieure à `debounce` + 200 ms, mesurée sur 100 occurrences |

## 4. Exigences — interface MCP

### 4.1 Transport et identification

| ID | Exigence | Critère d'acceptation |
|---|---|---|
| MCP-01 | Le serveur MCP expose le protocole JSON-RPC 2.0 conforme à la révision MCP retenue (D-01), transport HTTP streaming sur `127.0.0.1:8090`, chemin `/mcp`, ou transport stdio si D-02 le retient | Un client MCP de référence initialise la session et liste les outils sans erreur |
| MCP-02 | Le serveur déclare ses capacités : `tools` et `resources` uniquement ; `prompts`, `sampling` et `logging` non annoncés | La réponse `initialize` liste exactement ces capacités |
| MCP-03 | Le serveur est authentifié par jeton porteur ; toute requête sans jeton ou avec un jeton erroné reçoit `401` et aucune exécution | Appel sans jeton → 401, compteur d'audit incrémenté, aucune action |
| MCP-04 | Le serveur n'écoute que sur l'interface de boucle locale | `ss -ltnp` montre `127.0.0.1:8090`, jamais `0.0.0.0` |
| MCP-05 | Le nom et la version du serveur sont exposés et journalisés à la connexion | `initialize` retourne `serverInfo.name = "clawbot-bridge"` et la version du paquet |
| MCP-06 | Côté S2, la configuration est `/home/jetson/.hermes/config.yaml`, clé `mcp_servers.clawbot`, et les outils apparaissent sous le préfixe `mcp_clawbot_*` | `hermes` démarre, découvre les outils, et un appel de lecture retourne un contexte valide |

### 4.2 Catalogue d'outils — lecture de contexte

| Outil MCP | Entrée | Sortie | Annotation |
|---|---|---|---|
| `incident_list` | `{state?: "open"\|"closed", limit?: int}` | liste des incidents (id, trigger, sévérité, horodatage, état) | lecture seule |
| `incident_get` | `{incident_id}` | contexte complet de l'incident (§6) | lecture seule |
| `graph_snapshot` | `{include_qos?: bool}` | nœuds, topics, types, éditeurs, abonnés, QoS | lecture seule |
| `tf_snapshot` | `{root?: string, depth?: int}` | arêtes présentes, horodatage de chaque arête, cadres absents | lecture seule |
| `topic_stats` | `{topic, window_s?: int}` | cadence mesurée, âge du dernier message, taille moyenne, nombre d'éditeurs | lecture seule |
| `diagnostics` | `{level?: "ok"\|"warn"\|"error"\|"stale"}` | diagnostics agrégés, avec `unavailable[]` explicite | lecture seule |
| `param_get` | `{node, name}` | valeur, type, descripteur, bornes déclarées | lecture seule |
| `param_list` | `{node}` | paramètres du nœud avec type et valeur courante | lecture seule |
| `logs_tail` | `{since_iso?: string, limit?: int}` | dernières entrées du journal S1, structurées | lecture seule |
| `audit_tail` | `{incident_id?, limit?: int}` | dernières actions et décisions, avec identifiant de corrélation | lecture seule |
| `resources_snapshot` | `{}` | charge CPU, mémoire, température par zone, espace disque, tension | lecture seule |
| `capabilities` | `{}` | outils autorisés pour l'incident courant, limites effectives, prérequis manquants | lecture seule |

### 4.3 Catalogue d'outils — intervention

| Outil MCP | Capacité exigée | Entrée | Effet dans S1 | Annotation |
|---|---|---|---|---|
| `param_set` | Ajustement paramétrique | `{node, name, value, incident_id, justification}` | Écriture de paramètre ROS 2 via le service de paramètres, si le paramètre est dans la liste blanche et si la valeur est dans les bornes déclarées ; sinon refus motivé | mutation, bornée |
| `param_restore` | Ajustement paramétrique | `{node, name, incident_id}` | Rétablit la valeur d'avant l'incident, enregistrée par S1 | mutation, idempotente |
| `goal_list` | Réaffectation d'objectif | `{}` | Actions disponibles, objectifs actifs, état | lecture seule |
| `goal_cancel` | Réaffectation d'objectif | `{action, goal_id, incident_id}` | Annulation de l'objectif en cours par le client d'action de S1 | mutation, idempotente |
| `goal_send` | Réaffectation d'objectif | `{action, goal, incident_id, justification}` | Envoi d'un nouvel objectif si l'action est déclarée et si les prérequis sont présents | mutation |
| `safety_stop` | Escalade humaine | `{incident_id, reason}` | Arrêt immédiat par le superviseur, verrou d'arrêt posé, aucune reprise automatique | mutation, idempotente |
| `spec_propose` | Refactorisation et évolution | `{incident_id, exigence, changement, risques}` | Écrit un document de proposition dans le dépôt, sans exécution | écriture fichier |
| `patch_propose` | Refactorisation et évolution | `{incident_id, fichiers, diff, tests_prevus}` | Écrit un correctif sur une branche dédiée, sans build, sans déploiement | écriture fichier |
| `test_run` | Refactorisation et évolution | `{suite, incident_id}` | Exécute la suite de tests déclarée dans un environnement isolé, retourne code et sortie | lecture seule sur le robot |
| `escalate` | Escalade humaine | `{incident_id, motif, risque, action_demandee}` | Pose un état `ESCALATED`, notifie l'opérateur par le canal retenu (D-08), bloque les mutations | mutation, idempotente |

### 4.4 Contrat d'appel et d'erreur

| ID | Exigence | Critère d'acceptation |
|---|---|---|
| MCP-10 | Tout appel de mutation porte un `incident_id` ouvert et un identifiant d'action unique ; le rejeu du même identifiant est sans effet supplémentaire | Deux appels identiques produisent une seule mutation, la seconde retourne `status = "duplicate"` |
| MCP-11 | Toute réponse est un objet JSON `{status, data?, error?}` avec `status ∈ {ok, refused, duplicate, timeout, error}` | Aucune réponse en texte libre |
| MCP-12 | Toute erreur porte un code stable : `MCP-E-AUTH`, `MCP-E-ARG`, `MCP-E-MODE`, `MCP-E-BOUNDS`, `MCP-E-PREREQ`, `MCP-E-BUSY`, `MCP-E-TIMEOUT`, `MCP-E-INTERNAL` | Un test par code |
| MCP-13 | Un outil refusé par la politique de sûreté retourne `status = "refused"` avec le motif, sans effet de bord | Compteur d'effets de bord à zéro après refus |
| MCP-14 | Les mutations sont sérialisées par l'arbitre d'actionneurs de S1 : au plus une mutation active à la fois | Test de concurrence à 4 clients : aucune mutation concurrente, ordre déterministe |
| MCP-15 | `safety_stop` et `escalate` sont prioritaires sur toute mutation en cours et ne peuvent pas être bloqués par la file | Injection en cours de mouvement : arrêt effectif < 100 ms |
| MCP-16 | Le délai d'un appel de lecture est inférieur à 2 s ; un appel de mutation est acquitté en moins de 5 s ; `test_run` dispose de 120 s | Mesure sur 100 appels, p95 |
| MCP-17 | Le débit est limité à 60 appels de lecture par minute et à 10 mutations par minute ; au-delà, `MCP-E-BUSY` | Dépassement provoqué, refus explicite, aucune file infinie |
| MCP-18 | Chaque appel est journalisé avec `incident_id`, outil, arguments normalisés, décision de S1, résultat et durée | Journal corrélable de bout en bout |

### 4.5 Ressources MCP

| URI | Contenu | Mime |
|---|---|---|
| `incident://{incident_id}` | Contexte complet de l'incident, identique à `incident_get` | `application/json` |
| `spec://exigences` | Table des exigences de ce document (identifiants et critères) | `text/markdown` |
| `robot://limites` | Limites effectives : vitesses, couples, seuils, watchdogs, prérequis manquants | `application/json` |

## 5. Exigences — capacité de S2 et cycle d'intervention

| ID | Exigence | Critère d'acceptation |
|---|---|---|
| S2-01 | S2 n'est sollicité que par un incident de sévérité ≥ S2_MIN (D-03) et hors cooldown | Journal : chaque appel de S2 est adossé à un `incident_id` |
| S2-02 | Le contexte est transmis une seule fois, à l'ouverture de l'incident ; les mises à jour passent par les outils de lecture | Aucun appel d'outil sans contexte déjà fourni |
| S2-03 | S2 dispose d'un budget d'intervention borné (nombre d'outils appelés et durée) par incident (D-04) | Au dépassement, S1 clôt l'incident en `timed_out` et escalade |
| S2-04 | S2 ne peut pas élargir son propre jeu d'outils : la liste blanche est calculée par S1 à partir du déclencheur | Appel hors liste → `MCP-E-MODE` |
| S2-05 | Toute intervention se termine par un état explicite : `resolved`, `mitigated`, `escalated` ou `abandoned` | Aucun incident ne reste `open` sans décision après expiration du budget |
| S2-06 | Une proposition de refactorisation (`spec_propose`, `patch_propose`) n'a jamais d'effet sur le code en exécution ; son application exige une revue humaine et une reconstruction | Le binaire en cours d'exécution est identique avant et après appel (empreinte SHA-256 relevée) |

## 6. Structure du contexte transmis

### 6.1 Schéma

```json
{
  "schema_version": "1.0",
  "incident_id": "01JCH3...",
  "created_at": "2026-11-10T07:40:12.345+08:00",
  "trigger": {
    "id": "TRG-03",
    "severity": 2,
    "rule": "age(last_message) > 3 * declared_period",
    "observed": {"age_s": 4.2, "declared_period_s": 0.1},
    "threshold": {"max_age_s": 0.3},
    "debounce_s": 0.3,
    "occurrences": 3
  },
  "robot": {
    "host": "yahboom",
    "ros_distro": "humble",
    "ros_domain_id": 28,
    "bridge_version": "…",
    "mode": "standby",
    "uptime_s": 4631
  },
  "graph": {
    "nodes": [{"name": "/driver_node", "alive": true}],
    "topics": [
      {"name": "/voltage", "types": ["std_msgs/msg/Float32"],
       "publishers": 1, "subscribers": 1,
       "qos": {"reliability": "best_effort", "durability": "volatile", "depth": 10},
       "rate_hz": 10.0, "last_age_s": 0.12}
    ],
    "actions": [{"name": "/navigate_to_pose", "available": false}],
    "services": [{"name": "/driver_node/set_parameters", "available": true}]
  },
  "tf": {
    "frames_present": ["camera_link", "camera_color_frame"],
    "frames_expected_missing": ["base_link", "odom", "map"],
    "edges": [{"parent": "camera_link", "child": "camera_color_frame", "age_s": 0.02}],
    "stale": true
  },
  "diagnostics": {
    "items": [{"level": "error", "name": "bridge", "message": "…", "hardware_id": "…"}],
    "unavailable": ["/diagnostics: aucun éditeur"]
  },
  "params": [
    {"node": "/driver_node", "name": "angular_limit", "type": "double",
     "value": 5.0, "descriptor": {"read_only": false}}
  ],
  "resources": {
    "cpu_load_1m": 2.13,
    "memory_used_mb": 5805,
    "memory_total_mb": 15656,
    "disk_free_gb": 12.0,
    "thermal_c": {"cpu": 52.9, "tj": 53.0, "gpu": 50.5},
    "voltage_v": 11.9
  },
  "recent_commands": [
    {"at": "2026-11-10T07:39:58+08:00", "source": "llm", "tool": "SetVelocity",
     "args": {"linear_x": 0.06, "duration": 1.0}, "result": "ok"}
  ],
  "logs_tail": [{"at": "…", "level": "warn", "node": "/driver_node", "message": "…"}],
  "limits": {
    "max_linear_ms": 0.06, "max_angular_rs": 0.25,
    "motion_watchdog_s": 1.5, "allowed_params": ["angular_limit", "xlinear_limit"],
    "allowed_actions": ["/navigate_to_pose"]
  },
  "unavailable": ["/scan: aucune source", "/odom: topic absent"],
  "policy": {"s2_min_severity": 2, "budget": {"tool_calls": 8, "duration_s": 120}},
  "spec_refs": ["MCP-10", "TRG-03", "CTX-01"]
}
```

### 6.2 Exigences de contexte

| ID | Exigence | Critère d'acceptation |
|---|---|---|
| CTX-01 | Le contexte contient obligatoirement les blocs `schema_version`, `incident_id`, `created_at`, `trigger`, `robot`, `graph`, `tf`, `diagnostics`, `params`, `resources`, `limits`, `unavailable` | Validation par schéma JSON ; un bloc manquant fait échouer l'émission |
| CTX-02 | Toute donnée indisponible est déclarée dans `unavailable` avec le code (`ROS2-TOPIC-ABSENT`, `ROS2-ECHO-TIMEOUT`, `TF-FRAME-MISSING`, `ENOENT`) ; aucune valeur n'est inventée ni laissée à zéro sans marque | Sur ce robot, `/scan`, `/odom`, `base_link`, `odom`, `map` et l'état de charge batterie apparaissent systématiquement dans `unavailable` |
| CTX-03 | Chaque mesure porte son horodatage et son âge | Aucune valeur sans `age_s` ou `last_age_s` |
| CTX-04 | Le contexte est borné : 256 Ko maximum, `logs_tail` ≤ 200 entrées, `recent_commands` ≤ 50 entrées, `topics` ≤ 200 | Test avec graphe chargé : taille mesurée sous la borne |
| CTX-05 | Le contexte est identique en lecture répétée tant que l'incident n'a pas évolué, et horodaté sinon | Deux lectures consécutives sans changement → même contenu hors `read_at` |
| CTX-06 | Le contexte ne contient aucun secret : jetons, clés, chemins de credentials filtrés | Analyse statique du JSON sur 100 incidents générés |

## 7. Exigences — sûreté et invariants

| ID | Exigence | Critère d'acceptation |
|---|---|---|
| SAF-01 | Aucun outil MCP n'écrit sur un topic d'actionneur ; l'écriture passe uniquement par l'arbitre de S1 | Revue du catalogue : zéro outil de publication ; test d'injection de topic refusé |
| SAF-02 | Les limites effectives (vitesses, bornes de paramètres, actions autorisées) sont appliquées par S1, jamais déléguées à S2 | Test : valeur hors bornes → `MCP-E-BOUNDS`, aucune écriture |
| SAF-03 | `safety_stop` pose un verrou persistant : aucune reprise de mouvement sans action humaine explicite | Après `safety_stop`, toute mutation de mouvement → `MCP-E-MODE` |
| SAF-04 | Le canal MCP est authentifié, en boucle locale, et l'absence de jeton n'ouvre aucun droit | 401 systématique sans jeton |
| SAF-05 | Un incident de sévérité 4 n'autorise que `safety_stop` et `escalate` | Test par déclencheur de sévérité 4 |
| SAF-06 | La perte du canal MCP ne modifie pas le comportement de S1 : la surveillance, le watchdog et les politiques de reprise continuent | Coupure du canal pendant 60 s : aucun changement d'état des actionneurs |
| SAF-07 | Toute mutation est réversible ou explicitement marquée irréversible ; les mutations réversibles enregistrent la valeur antérieure | `param_set` suivi de `param_restore` retourne à la valeur initiale |
| SAF-08 | Le journal d'audit est en ajout seul, avec rotation, et conserve au minimum 30 jours d'incidents | Vérification de rotation et d'intégrité |

## 8. Exigences — traçabilité et développement

| ID | Exigence | Critère d'acceptation |
|---|---|---|
| TRC-01 | Chaque exigence de ce document porte un identifiant stable référencé par au moins un test | Matrice exigence → test complète, sans exigence orpheline |
| TRC-02 | Chaque déclencheur et chaque outil MCP possède un identifiant de spécification cité dans son test | Revue de la matrice |
| TRC-03 | Toute évolution de S1 issue d'une intervention de S2 référence l'`incident_id` d'origine et l'exigence modifiée | Le message de commit et la proposition portent ces références |
| TRC-04 | La suite de tests complète est exécutée avant et après chaque évolution de S1 | Deux rapports d'exécution joints à la proposition |
| TRC-05 | Le schéma du contexte et le catalogue d'outils sont versionnés ; un changement incompatible incrémente `schema_version` | Test de compatibilité entre versions |

## 9. Contraintes issues de l'état constaté

| ID | Contrainte | Origine |
|---|---|---|
| C-01 | Aucune source laser : aucun déclencheur ne peut dépendre de `/scan` | [[ERR-2026-11-10-001_absence_topic_scan]] |
| C-02 | Aucune odométrie ni TF `base_link`/`odom`/`map` : tout déclencheur TF et tout objectif de navigation doit traiter ces absences comme prérequis | [[ERR-2026-11-10-003_arbre_tf_incomplet]] |
| C-03 | Aucune jauge d'énergie système : seule la tension est disponible | [[batterie_principale]] |
| C-04 | Le champ d'action de S2 est limité aux actions réellement disponibles dans le graphe | [[ros2_graph_clawbot]] |
| C-05 | L'exposition réseau actuelle du pont (sans authentification, `0.0.0.0`) interdit l'ouverture du canal MCP avant correction | [[ERR-2026-11-10-004_execution_de_commande_non_authentifiee]] |

## 10. Paramètres manquants — décisions requises avant l'étape 2

Chaque ligne est une décision qui vous revient. La colonne « proposition » est une proposition
d'ingénierie, pas une hypothèse retenue : sans votre réponse, l'étape 2 ne peut pas être écrite.

| ID | Question | Proposition (à valider ou remplacer) |
|---|---|---|
| D-01 | Quelle révision du protocole MCP doit être cible ? (révisions connues : 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25) | 2025-06-18, la plus largement implémentée |
| D-02 | Transport du serveur MCP : HTTP streaming en boucle locale, ou stdio lancé par Hermes ? | HTTP streaming sur `127.0.0.1:8090` (survit aux redémarrages de S2, journalisation centralisée) |
| D-03 | Seuil `S2_MIN` : à partir de quelle sévérité S2 est-il sollicité ? | Sévérité ≥ 2 (degrés 3 et 4 traités aussi, 1 seule observé) |
| D-04 | Budget d'intervention par incident : nombre d'outils et durée | 8 appels, 120 s |
| D-05 | Valeurs de `debounce`, cooldown et débit d'incidents par déclencheur | `debounce` tel que §3.1 ; cooldown 60 s ; 6 incidents/h/déclencheur |
| D-06 | Seuil de tension basse batterie, et tension de coupure | 11,0 V alerte, 10,5 V arrêt (à confirmer selon la batterie réelle : 3S ou autre) |
| D-07 | Seuils de ressources : disque libre minimal, mémoire libre minimale, température maximale | 5 Go libres, 1 Go libre, 80 °C |
| D-08 | Canal d'escalade humaine : notification Hermes, courriel, message sur un bot, ou journal uniquement ? | Message Hermes + entrée d'audit ; à préciser |
| D-09 | Périmètre d'écriture de S2 dans le dépôt : branche dédiée uniquement, ou arbre de travail ? | Branche dédiée `s2/incident-<id>`, jamais la branche courante |
| D-10 | `test_run` : quelles suites sont autorisées (pytest Python, `colcon test` C++, les deux) et dans quel environnement (hôte ou conteneur) ? | Les deux, dans un conteneur dédié, sans accès aux actionneurs |
| D-11 | Qui détient le jeton MCP, où est-il stocké, et sa rotation est-elle exigée ? | `/etc/clawbot/mcp-token` (600, root:jetson), rotation trimestrielle |
| D-12 | Le pont C++ actuel (port 8000) est-il conservé comme base de S1, ou la fusion Python déjà recommandée est-elle préalable ? | Fusion Python préalable (voir [[llm2ros_bridge_coherence_et_approche]]) |
| D-13 | Les déclencheurs TRG-01 à TRG-14 sont-ils le jeu complet, ou faut-il en ajouter (perte de liaison série, erreur de checksum moteur, dérive d'IMU) ? | Jeu complet tel que proposé ; ajouts possibles |
| D-14 | L'opérateur peut-il refuser une proposition de S2 sans clore l'incident ? | Oui : état `refused_by_operator`, incident clos en `abandoned` |
| D-15 | **Écart constaté le 2026-11-10** : le SDK `mcp` 2.3.0 négocie la révision **2025-11-25**, pas 2025-06-18 (D-01). Amender D-01 ou épingler `mcp<2` ? | Amender D-01 vers 2025-11-25 : Hermes embarque déjà le SDK 2.3.0, donc serveur et client parlent la même révision. Épingler `mcp<2` maintiendrait 2025-06-18 au prix d'un SDK ancien côté serveur, avec une interopérabilité non vérifiée avec le client Hermes 2.x |

Mesure à l'origine de D-15 : session réelle entre un serveur `MCPServer` local et un client du même
poste, `initialize` retournant `protocol_version = "2025-11-25"` (détail et formes d'API vérifiées
dans [[llm2ros_mcp_test_plan]] §4.1). La révision n'est pas un choix documentaire : elle est négociée
par le SDK au démarrage de la session, donc D-01 ne peut être tenu qu'en épinglant la bibliothèque.

## 11. Voir aussi

- État constaté du pont : [[llm2ros_bridge]]
- Architecture actuelle, diagrammes : [[llm2ros_bridge_architecture]]
- Cahier des charges fonctionnel du pont : [[llm2ros_bridge_specification]]
- Analyse de cohérence et approche cible : [[llm2ros_bridge_coherence_et_approche]]
- Anomalies de référence : [[ERR-2026-11-10-001_absence_topic_scan]], [[ERR-2026-11-10-003_arbre_tf_incomplet]], [[ERR-2026-11-10-004_execution_de_commande_non_authentifiee]]
