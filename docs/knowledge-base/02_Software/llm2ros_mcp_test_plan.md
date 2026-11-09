---
title: "Plan de tests — pont LLM2ROS Système 1 / Système 2 (interface MCP)"
date: "2026-11-10T07:45:00+08:00"
author: "Hermes Agent"
tags: [software, ros2, mcp, tests, tdd, plan-de-tests, tracabilite]
status: actif
---

# Plan de tests — pont LLM2ROS S1 / S2

Étape 2 du projet. Spécification de référence : [[llm2ros_mcp_specification]] (validée le 2026-11-10).
Ce document définit l'architecture de la suite de tests, les doubles de test, l'isolation des
environnements, les critères d'acceptation et la matrice de traçabilité exigence → test.

## 1. Décisions validées qui contraignent les tests

| ID | Décision retenue | Conséquence sur les tests |
|---|---|---|
| D-01 | MCP révision 2025-06-18 | Tests de contrat écrits contre cette révision, `initialize` vérifié champ par champ |
| D-02 | HTTP streaming sur `127.0.0.1:8090` | Serveur lancé sur port éphémère en test, jamais 8090 ; un test vérifie le refus d'écoute hors boucle locale |
| D-03 | `S2_MIN = 2` | Un test par sévérité (1 → aucun appel S2, 2 → appel autorisé) |
| D-04 | Budget 8 appels / 120 s | Compteur injecté, pas d'attente réelle de 120 s |
| D-05 | `debounce` §3.1, cooldown 60 s, 6 incidents/h | Horloge injectée pour tous les tests de temporisation |
| D-06 | Batterie : alerte 11,0 V, coupure 10,5 V | Deux tests de seuil, alimentés par un faux `/voltage` |
| D-07 | Ressources : 5 Go, 1 Go, 80 °C | Sonde de ressources injectée, valeurs pilotées par scénario |
| D-08 | Escalade : message Hermes + audit | Canal d'escalade remplacé par un double, sortie inspectée |
| D-09 | Écriture S2 : branche `s2/incident-<id>` | Dépôt de test jetable, vérification de branche et d'absence de commit sur la branche courante |
| D-10 | `test_run` : pytest + `colcon test`, conteneur sans actionneurs | Runner de test simulé en unité, réel en test d'intégration marqué `slow` |
| D-11 | Jeton `/etc/clawbot/mcp-token`, 600, root:jetson | Jeton fourni par fixture temporaire, jamais le vrai fichier |
| D-12 | Fusion Python de S1 avant le serveur MCP | La suite cible une base **Python 3.10 / rclpy**, pas le binaire C++ actuel |
| D-13 | Jeu de déclencheurs clos | Un test d'invariant échoue si un déclencheur apparaît hors référentiel |
| D-14 | Refus opérateur → `abandoned` | Test d'état final explicite |

## 2. Principes

1. **Test avant code.** Chaque incrément de l'étape 4 commence par des tests rouges listés ici.
2. **Aucun test ne touche le robot réel.** Domaine DDS 99, boucle locale, ports éphémères, répertoires temporaires.
3. **Aucune temporisation réelle** pour les règles : l'horloge est injectée. Les seules attentes réelles sont des attentes d'événement bornées (≤ 2 s).
4. **Nominal sans S2, dégradé avec S2.** Les suites `TI` interdisent tout appel S2 : un incident y est un échec de test.
5. **Chaque test cite son exigence** dans son nom et dans sa docstring.
6. **Les invariants de sûreté sont testés en dernier recours, pas en dernier lieu** : un test de sûreté rouge bloque toute fusion, même si les autres passent.

## 3. Architecture de la suite

```text
tests/
├── conftest.py                  # fixtures communes, marqueurs, horloge, tmpdir
├── unit/                        # sans ROS, sans réseau, sans fichier hors tmpdir
│   ├── triggers/test_trg_XX.py          # un fichier par déclencheur (positif + négatif)
│   ├── context/test_ctx_builder.py      # assemblage, bornes, indisponibilités
│   ├── mcp/test_args_validation.py      # schémas d'entrée, codes d'erreur
│   ├── policy/test_budget.py            # budget d'intervention, cooldown, débit
│   └── policy/test_idempotency.py       # rejeu, duplicate
├── contract/                    # protocole MCP, JSON-RPC, schémas
│   ├── test_initialize.py
│   ├── test_tools_catalogue.py
│   ├── test_resources.py
│   ├── test_error_envelope.py
│   └── test_auth.py
├── integration/                 # ROS 2 réel, domaine 99, graphe simulé
│   ├── test_nominal_graph.py
│   ├── test_watchdog.py
│   ├── test_arbiter_serialization.py
│   ├── test_params.py
│   └── test_actions.py
├── degraded/                    # S2 simulé appelant le serveur MCP
│   ├── test_incident_flow.py
│   ├── test_tool_whitelist.py
│   ├── test_param_mutations.py
│   ├── test_goal_reassignment.py
│   ├── test_safety_stop_priority.py
│   ├── test_budget_expiry.py
│   └── test_channel_loss.py
├── safety/                      # invariants SAF et TRG-2x
│   ├── test_no_actuator_tool.py
│   ├── test_severity_4_locked.py
│   ├── test_stop_latch.py
│   └── test_audit_append_only.py
├── nonregression/
│   ├── test_golden_context.py
│   ├── test_catalogue_snapshot.py
│   └── test_full_chain.py
├── fixtures/
│   ├── scenarios/*.yaml          # conditions, valeurs capteurs, attendus
│   └── golden/context_v1.json    # contexte de référence
└── fakes/                        # doubles réutilisables, importables par les suites
```

Séparation imposée : `tests/fakes/` ne dépend d'aucun module de production ; les doubles implémentent
les interfaces déclarées, ce qui permet de tester la logique sans ROS.

## 4. Outillage et état vérifié sur ce poste

Relevé du 2026-11-10 07:44 CST, Python 3.10.12 (`/usr/bin/python3`) :

| Outil | État | Usage |
|---|---|---|
| `pytest` 9.2.0 | présent | exécution |
| `pytest-asyncio` 1.3.0 | présent | tests du serveur MCP et des flux asynchrones |
| `pytest-cov` 3.0.0 | présent (ancien, compatible avec avertissement) | couverture ; migration vers `coverage run` si rupture |
| `jsonschema` / `fastjsonschema` | présents | validation du schéma de contexte et des schémas d'outils |
| `pytest-mock`, `pytest-httpserver` | présents | doublures d'HTTP et de temps |
| `uvicorn`, `fastapi`, `httpx`, `aiohttp` | présents | faux service matériel, client HTTP |
| `rclpy`, `launch_testing`, `rcl_interfaces`, `action_msgs` | présents après `source /opt/ros/humble/setup.bash` | tests d'intégration ROS 2 |
| `mcp` (SDK) | **installé le 2026-11-10 : 2.3.0** dans le Python système (`~/.local`) et dans le venv Hermes | serveur, client, tests de contrat |
| `pytest-timeout` | **installé le 2026-11-10 : 2.4.0** | borne dure par test (ENV-06) |
| `hypothesis` | **installé le 2026-11-10 : 6.168.5** | tests de propriétés |
| `mutmut` | absent | optionnel : score de mutation |

Installation effectuée sur le Python système (`/usr/bin/python3 -m pip install --user`) ; les imports `rclpy`, `fastapi`, `uvicorn` et `starlette` ont été revérifiés après installation (voir §4.1). `pytest-cov` reste en 3.0.0 et n'a pas été touché ; `anyio` a été porté en 4.16.0 par la dépendance de `mcp`, sans rupture constatée.

### 4.1 API du SDK MCP vérifiée sur ce poste

Le SDK 2.x a renommé FastMCP en `MCPServer` et utilise des champs en `snake_case`. Les deux transports
requis par D-02 ont été exercés le 2026-11-10 07:37 CST, avec les résultats suivants.

| Vérification | Résultat mesuré |
|---|---|
| Serveur stdio minimal, 2 outils | `probe 0.1.0`, outils `['echo', 'add']`, appel `echo` → `bonjour du client`, `is_error = False` |
| Serveur HTTP streaming | écoute **`127.0.0.1:18090`** uniquement (`ss -ltn` : aucune entrée `0.0.0.0`), chemin `/mcp` |
| Session HTTP complète | `POST /mcp` 200 (initialize), `GET /mcp` 200 (flux), appels d'outils 200, `DELETE /mcp` 200 |
| Version de protocole négociée | **`2025-11-25`** avec le SDK 2.3.0 — voir D-15, écart avec D-01 |

Forme vérifiée côté serveur (à réutiliser à l'étape 3) :

```python
import asyncio
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

mcp = MCPServer(name="clawbot-bridge", version="0.1.0")

@mcp.tool(description="Renvoie le texte fourni.")
def echo(text: str) -> str:
    return text

# HTTP streaming, boucle locale, protection contre le rebinding DNS
asyncio.run(mcp.run_streamable_http_async(
    host="127.0.0.1", port=8090, streamable_http_path="/mcp",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:8090", "localhost:8090"],
    ),
))
```

Forme vérifiée côté client de test :

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async with streamable_http_client("http://127.0.0.1:8090/mcp") as streams:
    read_stream, write_stream = streams[0], streams[1]
    async with ClientSession(read_stream, write_stream) as session:
        init = await session.initialize()          # init.server_info, init.protocol_version
        tools = await session.list_tools()
        result = await session.call_tool("echo", {"text": "..."})  # result.content, result.is_error
```

Points d'API à ne pas confondre : `server_info` et `protocol_version` (et non `serverInfo`), `run_streamable_http_async` est une **coroutine** (à envelopper dans `asyncio.run`), et `mcp.server.fastmcp` n'existe plus.

## 5. Doubles de test

| Double | Interface simulée | Comportement pilotable | Utilisé par |
|---|---|---|---|
| `FakeClock` | horloge monotone et ROS time | avance manuelle, sauts, dérive | TU, TD (debounce, cooldown, budget) |
| `FakeGraph` | introspection du graphe | nœuds, topics, types, QoS, cadences, âges | TU, TC, TI |
| `FakeParamServer` | services de paramètres | valeurs, descripteurs, bornes, refus, lenteur | TU, TD |
| `FakeActionServer` | serveur d'action | succès, abandon, annulation, rejet, objectif bloqué | TU, TI, TD |
| `FakeHardwareService` | service matériel HTTP | 200, 422, 500, délai, corps tronqué | TI, TD |
| `FakeResourceProbe` | sonde système | CPU, RAM, disque, thermique, tension | TU, TD |
| `FakeAuditSink` | journal d'audit | capture en mémoire, vérification d'ordre et d'unicité | TU, TS |
| `FakeEscalationChannel` | canal opérateur | capture du message, échec d'envoi | TD |
| `McpTestClient` | client MCP | appels JSON-RPC bruts, jeton, session | TC, TD |
| `ScenarioLoader` | chargeur de scénarios YAML | paramètres -> fixtures | toutes |

## 6. Environnements et isolation

| Environnement | Marqueur | ROS | Réseau | Domaine DDS | Ce qu'il prouve |
|---|---|---|---|---|---|
| Unitaire | `unit` | non | non | — | logique de décision, calculs, schémas |
| Contrat | `contract` | non | port éphémère | — | conformité MCP et enveloppe d'erreur |
| Intégration | `ros` | oui | port éphémère | **99** | comportement nominal de S1 |
| Dégradé | `degraded` | oui | port éphémère | **99** | intervention S2, refus, priorités |
| Sûreté | `safety` | oui | port éphémère | **99** | invariants SAF, verrous |
| Matériel | `hardware` | oui | réel | 28 | **exclu par défaut**, exécution manuelle autorisée |

Règles d'isolation, toutes des exigences de test :

| ID | Règle | Vérification |
|---|---|---|
| ENV-01 | `ROS_DOMAIN_ID=99` obligatoire pour tout test `ros`, `degraded`, `safety` ; le domaine 28 est interdit | `conftest.py` échoue au démarrage si `ROS_DOMAIN_ID` vaut 28 |
| ENV-02 | `ROS_LOCALHOST_ONLY=1` et découverte restreinte à la boucle locale | variable posée par fixture de session |
| ENV-03 | Aucun port fixe : le serveur MCP et les faux services écoutent sur le port 0 | port relevé après démarrage |
| ENV-04 | Aucune écriture hors `tmp_path` ; le dépôt réel n'est jamais modifié | fixture de session qui échoue si un chemin absolu du dépôt est ouvert en écriture |
| ENV-05 | Aucun test n'appelle `systemctl`, `ros2 launch` d'un paquet installé, ni le pont en production | revue de code + intercepteur de sous-processus en mode strict |
| ENV-06 | Tout test est borné à 60 s (`pytest-timeout`), les tests `slow` à 180 s | configuration `pytest.ini` |

## 7. Suites, cas de test et attendus

### 7.1 Unitaire — déclencheurs (TU-TRG)

Un fichier `test_trg_<NN>.py` par déclencheur, avec exactement deux tests minimum :

| Cas | Attendu |
|---|---|
`test_trg_03_positive_sous_seuil_de_debounce` | aucun incident avant l'échéance
`test_trg_03_positive_apres_debounce` | un incident `TRG-03`, sévérité 2, contexte joint
`test_trg_03_negative_message_frais` | aucun incident
`test_trg_03_boundary_age_egal_seuil` | comportement défini à l'égalité (strictement supérieur) et documenté

S'applique à TRG-01 à TRG-14. Les règles TRG-20 à TRG-24 ont chacune un test d'invariant :

| Test | Invariant |
|---|---|
| `test_trg_20_no_duplicate_incident` | même déclencheur + même sujet → 1 incident, compteur à 2 |
| `test_trg_21_cooldown_suppresses` | 2ᵉ occurrence dans le cooldown → aucun incident, journal `COOLDOWN` |
| `test_trg_22_policy_resolves_without_s2` | politique de reprise applicable → incident clos, zéro appel S2 |
| `test_trg_23_severity_4_tools` | sévérité 4 → `capabilities` ne liste que `safety_stop` et `escalate` |
| `test_trg_24_closed_trigger_set` | le registre des déclencheurs est exactement TRG-01..14, sinon échec |

### 7.2 Unitaire — contexte (TU-CTX)

| Test | Exigence | Attendu |
|---|---|---|
| `test_ctx_required_blocks` | CTX-01 | chaque bloc absent → erreur de validation |
| `test_ctx_unavailable_declared` | CTX-02 | `/scan`, `/odom`, `base_link`, SoC présents dans `unavailable` avec code |
| `test_ctx_no_silent_zero` | CTX-02 | une mesure sans valeur porte `null` + code, jamais `0.0` |
| `test_ctx_age_present` | CTX-03 | toute mesure possède `age_s` ou `last_age_s` |
| `test_ctx_size_bounded` | CTX-04 | graphe à 200 topics, 200 logs, 50 commandes → ≤ 256 Ko |
| `test_ctx_stable_read` | CTX-05 | deux lectures sans changement → identiques hors `read_at` |
| `test_ctx_no_secret` | CTX-06 | motif `token`, `key=`, `Bearer` absent sur 100 contextes générés |
| `test_ctx_schema_versions` | TRC-05 | `schema_version` inconnue → refus explicite côté client |

### 7.3 Contrat MCP (TC)

| Test | Exigence | Attendu |
|---|---|---|
| `test_initialize_capabilities` | MCP-02 | capacités exactement `tools` + `resources` |
| `test_initialize_server_info` | MCP-05 | `name = clawbot-bridge`, version non vide |
| `test_tools_names_match_spec` | MCP-02 | 22 outils exactement, noms conformes au §4.2-4.3 |
| `test_tools_descriptors_valid` | MCP-02 | chaque `inputSchema` valide contre JSON Schema 2020-12 |
| `test_tools_annotations` | MCP-03/SAF-01 | toute mutation porte `destructiveHint`, aucune ne publie sur un topic |
| `test_resources_uris` | §4.5 | `incident://{id}`, `spec://exigences`, `robot://limites` résolvent |
| `test_error_envelope` | MCP-11, MCP-12 | 8 codes couverts, enveloppe `{status, error}` |
| `test_auth_missing_token` | MCP-03, SAF-04 | 401, zéro effet de bord |
| `test_auth_wrong_token` | MCP-03 | 401 constant (comparaison à temps constant vérifiée par mesure de variance < 5 %) |
| `test_listen_loopback_only` | MCP-04 | socket non joignable depuis l'adresse LAN du robot |

### 7.4 Intégration nominale S1 (TI)

| Test | Exigence | Attendu |
|---|---|---|
| `test_nominal_graph_no_incident` | TRG-01..09 | graphe complet, cadences nominales, 30 s simulées → 0 incident, 0 appel S2 |
| `test_watchdog_stops_after_timeout` | SAF-02 | commande puis silence 1,5 s → vitesse nulle publiée |
| `test_arbiter_serializes_actions` | MCP-14 | 4 clients concurrents → ordre déterministe, aucune imbrication |
| `test_params_read` | MCP-02 | `param_list` restitue type et valeur |
| `test_action_goal_success` | TRG-10 | objectif accepté, suivi jusqu'au succès |
| `test_voltage_rate_10hz` | TRG-04 | cadence mesurée dans la fenêtre attendue |
| `test_audit_written` | MCP-18 | une entrée par action, corrélée |

### 7.5 Comportement dégradé (TD)

| Test | Exigence | Attendu |
|---|---|---|
| `test_incident_opens_and_context_served` | S2-01, S2-02 | incident sévérité 2 → contexte complet servi une fois |
| `test_severity_1_never_calls_s2` | D-03 | sévérité 1 → aucun appel, incident journalisé |
| `test_tool_whitelist_enforced` | S2-04 | outil hors liste → `MCP-E-MODE` |
| `test_param_set_applied_in_bounds` | MCP-01, SAF-07 | valeur appliquée, ancienne valeur enregistrée |
| `test_param_set_out_of_bounds_refused` | SAF-02 | `MCP-E-BOUNDS`, valeur inchangée |
| `test_param_restore_returns_previous` | SAF-07 | retour exact à la valeur antérieure |
| `test_goal_cancel_then_send` | MCP-01 | annulation effective puis nouvel objectif accepté |
| `test_goal_send_missing_prereq` | MCP-12 | `MCP-E-PREREQ` (TF absent) |
| `test_safety_stop_preempts_motion` | MCP-15 | arrêt < 100 ms pendant mouvement |
| `test_escalate_blocks_mutations` | SAF-05 | après `escalate`, toute mutation → `MCP-E-MODE` |
| `test_budget_expiry_escalates` | S2-03, S2-05 | 9ᵉ appel → incident `timed_out`, escalade |
| `test_duplicate_call_is_idempotent` | MCP-10 | second appel → `duplicate`, une seule mutation |
| `test_rate_limit_busy` | MCP-17 | 11ᵉ mutation/min → `MCP-E-BUSY` |
| `test_channel_loss_leaves_s1_intact` | SAF-06 | coupure 60 s simulée → état actionneurs inchangé |
| `test_proposal_never_touches_runtime` | S2-06 | empreinte du binaire identique avant/après `patch_propose` |

### 7.6 Sûreté (TS)

| Test | Exigence | Attendu |
|---|---|---|
| `test_no_tool_publishes_actuator` | SAF-01 | analyse statique du catalogue + interception runtime : zéro publication |
| `test_severity_4_open_tools` | SAF-05, TRG-23 | liste réduite à deux outils |
| `test_safety_stop_latch_persists` | SAF-03 | verrou maintenu après redémarrage du serveur MCP |
| `test_audit_append_only_and_rotation` | SAF-08 | aucune réécriture, rotation à la taille, 30 jours |
| `test_irreversible_marked` | SAF-07 | toute mutation irréversible porte le drapeau |

### 7.7 Non-régression (TN)

| Test | Rôle |
|---|---|
| `test_golden_context` | le contexte d'un scénario de référence reste identique au fichier `fixtures/golden/context_v1.json` (hors horodatages) ; toute évolution exige un bump de `schema_version` |
| `test_catalogue_snapshot` | empreinte SHA-256 des 22 schémas d'outils figée ; modification = revue explicite |
| `test_full_chain` | scénario complet : trigger → incident → contexte → décision simulée → mutation → vérification → audit |
| `test_triggers_registry_complete` | TRG-24 |

## 8. Critères d'acceptation de la suite

| ID | Critère | Seuil |
|---|---|---|
| ACC-01 | Couverture des déclencheurs | 100 % des TRG-01..14 ont un test positif et un test négatif |
| ACC-02 | Couverture du modèle d'erreur | 100 % des 8 codes `MCP-E-*` |
| ACC-03 | Couverture de branches de la logique de décision (`s1/decisions/`, `s1/context/`) | ≥ 85 % |
| ACC-04 | Invariants de sûreté | 100 % verts, jamais marqués `skip` |
| ACC-05 | Durée totale hors `slow` | ≤ 5 min sur le Jetson |
| ACC-06 | Tests instables | 0 ; un test instable est corrigé ou quarantiné avec ticket, jamais relancé en boucle |
| ACC-07 | Déterminisme | deux exécutions consécutives → mêmes résultats, mêmes durées à ±20 % |
| ACC-08 | Isolation | aucun accès au domaine 28, aucun port fixe, aucune écriture hors `tmp_path` |

## 9. Matrice de traçabilité

| Exigence | Tests |
|---|---|
| TRG-01..09 | `test_trg_01..09_positive/negative`, `test_nominal_graph_no_incident` |
| TRG-10 | `test_trg_10_*`, `test_action_goal_success` |
| TRG-11 | `test_trg_11_*`, `test_watchdog_stops_after_timeout` |
| TRG-12 | `test_trg_12_*` |
| TRG-13, TRG-14 | `test_trg_13_*`, `test_trg_14_*` |
| TRG-20..24 | `test_trg_20..24_*` (TS + TN) |
| MCP-01 | `test_initialize_*`, `test_param_set_applied_in_bounds`, `test_goal_cancel_then_send` |
| MCP-02 | `test_tools_names_match_spec`, `test_tools_descriptors_valid`, `test_params_read` |
| MCP-03 | `test_auth_missing_token`, `test_auth_wrong_token` |
| MCP-04 | `test_listen_loopback_only` |
| MCP-05 | `test_initialize_server_info` |
| MCP-06 | `test_full_chain` (client Hermes réel, marqué `slow`) |
| MCP-10 | `test_duplicate_call_is_idempotent` |
| MCP-11, MCP-12 | `test_error_envelope`, `test_goal_send_missing_prereq` |
| MCP-13 | `test_param_set_out_of_bounds_refused` |
| MCP-14 | `test_arbiter_serializes_actions` |
| MCP-15 | `test_safety_stop_preempts_motion` |
| MCP-16 | `test_latency_lecture_p95`, `test_latency_mutation_p95` (mesures sur faux graphe) |
| MCP-17 | `test_rate_limit_busy` |
| MCP-18 | `test_audit_written`, `test_audit_append_only_and_rotation` |
| CTX-01..06 | `test_ctx_*` |
| S2-01..05 | `test_incident_opens_and_context_served`, `test_severity_1_never_calls_s2`, `test_budget_expiry_escalates` |
| S2-06 | `test_proposal_never_touches_runtime` |
| SAF-01..08 | `test_no_tool_publishes_actuator`, `test_severity_4_open_tools`, `test_safety_stop_latch_persists`, `test_auth_*`, `test_audit_*`, `test_channel_loss_leaves_s1_intact` |
| TRC-01..05 | `test_triggers_registry_complete`, `test_catalogue_snapshot`, `test_golden_context` |
| ENV-01..06 | fixtures de `conftest.py`, vérifiées par `test_environment_isolation` |

## 10. Incréments TDD et ordre d'écriture (entrée de l'étape 3)

| Incrément | Tests à écrire d'abord (rouges) | Code attendu ensuite |
|---|---|---|
| I1 | `TC-*` (contrat) : `initialize`, `list_tools`, `call_tool` vide, auth | Squelette du serveur MCP, catalogue typé, enveloppe d'erreur |
| I2 | `TU-TRG-01..14` et `TRG-20..24` | Registre de déclencheurs, évaluateur, horloge injectée |
| I3 | `TU-CTX-01..06` | Assembleur de contexte et sérialisation |
| I4 | `TS-*` (sûreté) | Arbitre, verrous, journal d'audit |
| I5 | `TD-*` (dégradé) | Câblage des 10 outils d'intervention sur l'arbitre |
| I6 | `TN-*` (non-régression) | Figement des schémas et du contexte de référence |

## 11. Risques de test et mitigations

| Risque | Mitigation |
|---|---|
| Découverte DDS instable sur Jetson (mémoire partagée FastDDS) | `ROS_LOCALHOST_ONLY=1`, profil FastDDS dédié aux tests, attente d'événement bornée, jamais de `sleep` fixe |
| `pytest-cov` 3.0.0 ancien avec pytest 9 | surveiller l'avertissement ; repli sur `coverage run -m pytest` si rupture |
| `mcp` absent du Python système | tests de contrat écrits en JSON-RPC brut (httpx) ; un seul test SDK marqué `slow` |
| Latences de mesure sur Jetson (CPU partagé) | seuils p95 larges (2 s / 5 s), mesures répétées, pas de seuil serré sur les tests unitaires |
| Écritures dans le dépôt par `patch_propose` | dépôt jetable par test, vérification par `git status` et empreinte |
| Horloge ROS et horloge système divergentes | horloge unique injectée, jamais `time.time()` dans la logique testée |

## 12. Ce que cette suite ne prouve pas

- Elle ne prouve pas l'innocuité physique du robot (pas de HIL par défaut, pas de source laser, TF incomplet).
- Elle ne prouve pas la qualité des décisions du modèle de langage : seul le contrat d'outils et les garde-fous sont testés.
- Elle ne teste pas le binaire C++ actuel, hors périmètre après D-12.

## 14. Étape 3 — squelettes de tests livrés (état rouge)

Les squelettes sont écrits, exécutables et **rouges pour la bonne raison** : le serveur n'existe pas
encore (étape 4). Aucune logique n'a été écrite, seule la signature de l'interface est figée.

| Élément livré | Rôle |
|---|---|
| `bridge_mcp/contract.py` | Données de spécification : 22 outils, 13 lectures et 9 mutations, 8 codes d'erreur, 5 statuts, 3 ressources, 4 topics d'actionneurs interdits, révision `2025-11-25` |
| `bridge_mcp/server.py` | Interface publique : `create_server(*, token, host, port)` et `streamable_http_app(server)` — lèvent `NotImplementedError` |
| `tests/mcp_bridge/pytest.ini` | `asyncio_mode = auto`, `--timeout=60`, marqueurs `contract`, `ros`, `degraded`, `safety`, `hardware`, `slow`, `pythonpath = ../..` |
| `tests/mcp_bridge/conftest.py` | Refus du domaine DDS 28, jeton de test unique, fixture `connected` (session MCP initialisée une seule fois) |
| `tests/mcp_bridge/support/harness.py` | Démarrage du serveur sur port éphémère en boucle locale, mesure de joignabilité LAN |
| `contract/test_initialize.py` | MCP-02, MCP-05, D-15 |
| `contract/test_catalogue.py` | 22 outils, schémas JSON Schema 2020-12, annotations lecture/mutation, aucun topic d'actionneur |
| `contract/test_auth_transport.py` | 401 sans jeton et jeton erroné, écoute boucle locale, injoignabilité LAN, en-tête `Host` étranger refusé, pas de fuite de jeton |
| `contract/test_error_envelope.py` | Taxonomie fermée, outil inconnu typé, argument manquant, refus motivé |
| `contract/test_resources.py` | Ressources statiques, modèle d'incident, contenu du bloc de limites |

Exécution du 2026-11-10 07:52 CST :

```
$ cd tests/mcp_bridge && python3 -m pytest
1 passed, 22 errors in 1.42s

E   NotImplementedError: étape 4 : implémentation du serveur MCP (catalogue, authentification, contexte)
../../bridge_mcp/server.py:33: NotImplementedError
```

Le seul test vert (`test_error_taxonomy_is_closed`) porte sur les constantes de spécification, pas sur
le serveur. Les 22 autres échouent sur `NotImplementedError`, jamais sur une erreur de collecte :
l'environnement de test est donc valide, seul le code manque.

## 15. Voir aussi

- Spécification des exigences : [[llm2ros_mcp_specification]]
- État constaté du pont : [[llm2ros_bridge]]
- Architecture actuelle et diagrammes : [[llm2ros_bridge_architecture]]
- Analyse de cohérence et cible : [[llm2ros_bridge_coherence_et_approche]]
- Contraintes matérielles : [[ERR-2026-11-10-001_absence_topic_scan]], [[ERR-2026-11-10-003_arbre_tf_incomplet]]
