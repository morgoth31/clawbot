---
title: "Matrice de traçabilité — exigence vers test"
date: "2026-11-10T13:27:48+08:00"
author: "Hermes Agent"
tags: [software, tracabilite, tests, exigences, qualite]
status: actif
generated: true
---

# Matrice de traçabilité — exigence vers test

Page régénérée par `scripts/generate_traceability.py` le 2026-11-10T13:27:48+08:00. Elle ne se modifie pas à la main : toute évolution vient des spécifications ou des tests.

## 1. Synthèse

| Indicateur | Valeur |
|---|---|
| Exigences identifiées | 115 |
| Exigences couvertes par au moins un test | 45 |
| Exigences sans test | 70 |
| Fichiers de test analysés | 15 |
| Identifiants cités mais non spécifiés | 1 |

## 2. Matrice

| Exigence | Énoncé | Document | Tests |
|---|---|---|---|

### llm2ros_bridge_specification.md — 0/40 exigences citées par un test

| Exigence | Énoncé | Tests |
|---|---|---|
| `EF-01` | Le service publie la totalité de ses capacités sous forme de schémas JSON conformes au sous-ensemble OpenAI (type, fu… | — **non couverte** |
| `EF-02` | Les schémas sont générés depuis une source unique, partagée avec la validation serveur et la documentation | — **non couverte** |
| `EF-03` | Chaque réponse est un objet JSON structuré {"ok":bool, "data":object, "error":{"code","message"}} | — **non couverte** |
| `EF-04` | Le champ arguments est accepté en objet JSON et en chaîne JSON encodée | — **non couverte** |
| `EF-05` | Les erreurs sont typées par un code stable (E_INVALID_ARG, E_UNKNOWN_TOOL, E_MODE_FORBIDDEN, E_HW_UNREACHABLE, E_TIME… | — **non couverte** |
| `EF-06` | La version sémantique du service est exposée (/health, en-tête) et le code source est versionné | — **non couverte** |
| `EF-07` | Une spécification OpenAPI 3.1 est servie et décrit toutes les routes | — **non couverte** |
| `EF-08` | Chaque requête reçoit un identifiant de corrélation, retourné au client (X-Request-Id et champ request_id) | — **non couverte** |
| `EF-09` | L'identifiant de corrélation est présent dans chaque journal d'exécution, avec outil, arguments normalisés, mode, rés… | — **non couverte** |
| `EF-10` | Les appels d'outils bruts du LLM sont archivés pour audit (horodatage, nom, arguments, réponse) | — **non couverte** |
| `EF-11` | Toute commande de vitesse porte une durée bornée, et l'arrêt effectif survient au plus tard 300 ms après l'échéance | — **non couverte** |
| `EF-12` | Une seule commande de mouvement est active à la fois : les commandes concurrentes sont sérialisées ou rejetées avec u… | — **non couverte** |
| `EF-13` | Stop est prioritaire sur toute autre commande et s'exécute même lorsqu'une action est en cours | — **non couverte** |
| `EF-14` | Le watchdog d'arrêt est indépendant du client HTTP et du processus serveur | — **non couverte** |
| `EF-15` | Les bornes de vitesse ont une source unique de vérité, identique dans le schéma, la validation, le service matériel e… | — **non couverte** |
| `EF-16` | Une commande de navigation n'est acceptée que si ses prérequis sont présents : odométrie, transformation map→odom→bas… | — **non couverte** |
| `EF-17` | La navigation s'appuie sur un contrôleur en boucle fermée (Nav2) ; aucun déplacement en boucle ouverte n'est exposé s… | — **non couverte** |
| `EF-18` | Le référentiel des coordonnées cibles est déclaré et vérifié à l'exécution | — **non couverte** |
| `EF-19` | L'ensemble des caméras disponibles est découvert à l'exécution et publié dans les schémas (énumération) | — **non couverte** |
| `EF-20` | Une capture renvoie le chemin du fichier, les métadonnées (largeur, hauteur, horodatage) et l'image, avec une taille … | — **non couverte** |
| `EF-21` | Une caméra indisponible produit E_CAMERA_UNAVAILABLE avec le périphérique attendu et non une erreur générique | — **non couverte** |
| `EF-22` | La détection d'objets renvoie detection_count, inference_ms et la liste des boîtes au format vision_msgs ou équivalen… | — **non couverte** |
| `EF-23` | Les angles articulaires sont validés en cardinalité, en type et en borne avant tout envoi au matériel | — **non couverte** |
| `EF-24` | Chaque articulation est bornée dans le schéma et dans la validation | — **non couverte** |
| `EF-25` | La pince accepte exactement deux états et retourne l'angle appliqué | — **non couverte** |
| `EF-26` | Une pose nommée est identifiée par un identifiant borné, et son contenu est publié en lecture | — **non couverte** |
| `EF-27` | La synthèse vocale n'exécute aucun interpréteur de commandes : l'argument texte est transmis comme un argument de pro… | — **non couverte** |
| `EF-28` | Le texte de synthèse est borné en longueur (≤ 300 caractères) et normalisé | — **non couverte** |
| `EF-29` | La reconnaissance vocale soit renvoie une transcription, soit retourne E_FEATURE_UNAVAILABLE avec le prérequis manquant | — **non couverte** |
| `EF-30` | Les paramètres de LED et de buzzer sont bornés et validés côté serveur | — **non couverte** |
| `EF-31` | La tension est publiée avec son horodatage et un indicateur de péremption | — **non couverte** |
| `EF-32` | L'état de charge est calculé selon une courbe déclarée et documentée, ou marqué indisponible | — **non couverte** |
| `EF-33` | La télémétrie agrégée (IMU, vitesse, servos, énergie) est exposée au LLM | — **non couverte** |
| `EF-34` | Le mode courant restreint l'ensemble des outils exécutables | — **non couverte** |
| `EF-35` | Le passage de mode exécute ses préconditions (arrêt, position de bras, signalisation) de manière atomique | — **non couverte** |
| `EF-36` | Le mode est persistant et son état initial est explicite au démarrage | — **non couverte** |
| `EF-37` | Les routes d'exploitation et de développement (build, test, maintenance) sont soumises au mode et à l'authentificatio… | — **non couverte** |
| `EF-38` | /health distingue vivacité du processus et disponibilité de la chaîne ROS 2 et du service matériel | — **non couverte** |
| `EF-39` | L'arrêt du service remet les actionneurs en état sûr et publie une vitesse nulle | — **non couverte** |
| `EF-40` | Les fonctions de cartographie (démarrage/arrêt SLAM, sauvegarde, liste, lecture d'image) sont soit exposées avec leur… | — **non couverte** |

### llm2ros_health_test_specification.md — 15/18 exigences citées par un test

| Exigence | Énoncé | Tests |
|---|---|---|
| `HLT-01` | L'inventaire des périphériques est déclaratif, versionné et unique ; il porte l'identité attendue, le caractère requi… | `test_inventory::test_every_peripheral_declares_its_identity_and_probe_levels`, `test_inventory::test_inventory_declares_nine_peripherals_with_stable_ids` |
| `HLT-02` | Chaque périphérique est identifié par son identité matérielle (couple VID:PID, chemin by-id, série si disponible), ja… | `test_inventory::test_every_peripheral_declares_its_identity_and_probe_levels`, `test_inventory::test_identity_is_never_an_index`, `test_probes::test_foreign_device_on_the_expected_index_is_a_mismatch`, `test_probes::test_moved_video_index_is_still_found` |
| `HLT-03` | Trois niveaux de sonde indépendants : device, ros, functional ; un niveau en échec n'empêche pas les autres de rendre… | `test_probes::test_camera_device_present_but_topic_silent_keeps_levels_independent` |
| `HLT-04` | Aucune sonde ne retourne un booléen nu : toute mesure porte observed, threshold, measured_at, et un error_code en cas… | `test_probes::test_serial_device_held_by_two_processes_is_reported`, `test_report::test_every_peripheral_carries_a_complete_probe_contract` |
| `HLT-05` | Toute sonde a un délai borné ; le rapport complet est produit en moins de 10 s, aucune sonde ne dépasse 2 s | `test_notify::test_http_failure_is_reported_without_retry_loop`, `test_report::test_measured_window_is_shared_between_topics` |
| `HLT-06` | Le test n'écrit rien : aucun fichier hors --report <chemin>, aucune publication, aucun param_set, aucun redémarrage d… | `test_probes::test_serial_device_held_by_two_processes_is_reported` |
| `HLT-07` | Le rapport est un JSON stable et versionné (health_version) ; deux exécutions sans changement donnent les mêmes verdi… | `test_report::test_peripherals_follow_inventory_order`, `test_report::test_report_is_bounded_and_free_of_secrets`, `test_report::test_two_runs_without_change_give_the_same_verdicts` |
| `HLT-08` | Un périphérique déclaré non installé (lidar) est unavailable avec HLT-E-NOT-INSTALLED, jamais failed ni ignoré | `test_inventory::test_lidar_is_declared_not_installed_not_missing`, `test_inventory::test_report_marks_lidar_unavailable` |
| `HLT-09` | Un failed sur un périphérique requis: false n'abaisse pas le verdict global, mais figure dans le rapport et le journal | `test_probes::test_optional_peripheral_failure_does_not_degrade_global_verdict` |
| `HLT-10` | Un service systemd actif ne vaut pas preuve de présence : le verdict repose sur le périphérique et les données, jamai… | `test_probes::test_optional_peripheral_failure_does_not_degrade_global_verdict` |
| `HLT-11` | La sonde ros initialise un contexte rclpy en lecture seule dans le domaine courant, ne crée aucun éditeur, et le détr… | — **non couverte** |
| `HLT-12` | Interface ligne de commande avec sortie JSON et codes de sortie 0/1/2/3 | `test_report::test_cli_prints_json_and_returns_the_verdict_code`, `test_report::test_exit_codes_follow_the_verdict` |
| `HLT-13` | Le rapport alimente l'outil MCP diagnostics et la ressource health://etat sans duplication de logique | `test_diagnostics::test_diagnostics_refuses_when_no_report_exists`, `test_diagnostics::test_diagnostics_returns_the_last_health_report` |
| `HLT-14` | Le test de santé ne redéfinit aucune règle de déclenchement : il alimente Observation, TriggerEngine décide | — **non couverte** |
| `HLT-15` | Exécution au démarrage par unité oneshot, et à chaque anomalie émise par S1 ; aucune exécution périodique, aucune act… | `test_report::test_service_mode_returns_zero_even_when_verdict_is_failed` |
| `HLT-16` | Chaque verdict cite l'exigence et l'inventaire qui le justifient (spec_refs) | — **non couverte** |
| `HLT-17` | Aucun secret, aucun jeton, aucun chemin de credentials dans le rapport | `test_notify::test_token_never_appears_in_the_report_or_the_message`, `test_report::test_report_is_bounded_and_free_of_secrets` |
| `HLT-18` | Aucune donnée inventée : une mesure impossible est null avec code, jamais 0 ni false implicite | `test_diagnostics::test_diagnostics_refuses_when_no_report_exists`, `test_notify::test_absent_token_file_is_reported_not_invented`, `test_probes::test_http_endpoint_failure_is_reported`, `test_probes::test_missing_measurement_is_null_with_a_code_never_zero` |

### llm2ros_mcp_specification.md — 30/57 exigences citées par un test

| Exigence | Énoncé | Tests |
|---|---|---|
| `CTX-01` | Le contexte contient obligatoirement les blocs schema_version, incident_id, created_at, trigger, robot, graph, tf, di… | `test_context::test_context_contains_every_required_block`, `test_incident_context::test_incident_get_returns_the_context_of_the_specification`, `test_incident_context::test_incident_get_without_measurement_stays_honest`, `test_resources::test_limits_resource_documents_effective_bounds` |
| `CTX-02` | Toute donnée indisponible est déclarée dans unavailable avec le code (ROS2-TOPIC-ABSENT, ROS2-ECHO-TIMEOUT, TF-FRAME-… | `test_context::test_unavailable_data_is_declared_with_a_code` |
| `CTX-03` | Chaque mesure porte son horodatage et son âge | `test_context::test_context_measures_carry_their_age` |
| `CTX-04` | Le contexte est borné : 256 Ko maximum, logs_tail ≤ 200 entrées, recent_commands ≤ 50 entrées, topics ≤ 200 | `test_context::test_context_is_bounded_in_size` |
| `CTX-05` | Le contexte est identique en lecture répétée tant que l'incident n'a pas évolué, et horodaté sinon | `test_context::test_context_is_stable_between_reads` |
| `CTX-06` | Le contexte ne contient aucun secret : jetons, clés, chemins de credentials filtrés | `test_context::test_context_carries_no_secret` |
| `MCP-01` | Le serveur MCP expose le protocole JSON-RPC 2.0 conforme à la révision MCP retenue (D-01), transport HTTP streaming s… | — **non couverte** |
| `MCP-02` | Le serveur sert tools et resources ; aucun prompt n'est enregistré ni servi ; sampling et logging non annoncés. *(Ame… | `test_catalogue::test_catalogue_has_exactly_the_specified_tools`, `test_catalogue::test_each_tool_schema_is_valid_json_schema`, `test_initialize::test_capabilities_tools_and_resources_without_prompts` |
| `MCP-03` | Le serveur est authentifié par jeton porteur ; toute requête sans jeton ou avec un jeton erroné reçoit 401 et aucune … | `test_auth_transport::test_request_with_valid_token_is_accepted`, `test_auth_transport::test_request_with_wrong_token_is_rejected`, `test_auth_transport::test_request_without_token_is_rejected` |
| `MCP-04` | Le serveur n'écoute que sur l'interface de boucle locale | `test_auth_transport::test_host_header_outside_allowlist_is_refused`, `test_auth_transport::test_listen_address_is_loopback_only`, `test_auth_transport::test_port_is_not_reachable_from_lan_address` |
| `MCP-05` | Le nom et la version du serveur sont exposés et journalisés à la connexion | `test_initialize::test_server_identity` |
| `MCP-06` | Côté S2, la configuration est /home/jetson/.hermes/config.yaml, clé mcp_servers.clawbot, et les outils apparaissent s… | — **non couverte** |
| `MCP-10` | Tout appel de mutation porte un incident_id ouvert et un identifiant d'action unique ; le rejeu du même identifiant e… | `test_incident_context::test_incident_get_returns_the_context_of_the_specification` |
| `MCP-11` | Toute réponse est un objet JSON {status, data?, error?} avec status ∈ {ok, refused, duplicate, timeout, error} | — **non couverte** |
| `MCP-12` | Toute erreur **levée par le pont** porte un code stable : MCP-E-AUTH, MCP-E-ARG, MCP-E-MODE, MCP-E-BOUNDS, MCP-E-PRER… | `test_error_envelope::test_error_taxonomy_is_closed`, `test_error_envelope::test_missing_required_argument_is_rejected`, `test_error_envelope::test_unknown_tool_is_refused_without_success` |
| `MCP-13` | Un outil refusé par la politique de sûreté retourne status = "refused" avec le motif, sans effet de bord | `test_error_envelope::test_refusal_reports_a_reason` |
| `MCP-14` | Les mutations sont sérialisées par l'arbitre d'actionneurs de S1 : au plus une mutation active à la fois | — **non couverte** |
| `MCP-15` | safety_stop et escalate sont prioritaires sur toute mutation en cours et ne peuvent pas être bloqués par la file | `test_catalogue::test_priority_tools_are_present` |
| `MCP-16` | Le délai d'un appel de lecture est inférieur à 2 s ; un appel de mutation est acquitté en moins de 5 s ; test_run dis… | — **non couverte** |
| `MCP-17` | Le débit est limité à 60 appels de lecture par minute et à 10 mutations par minute ; au-delà, MCP-E-BUSY | — **non couverte** |
| `MCP-18` | Chaque appel est journalisé avec incident_id, outil, arguments normalisés, décision de S1, résultat et durée | — **non couverte** |
| `SAF-01` | Aucun outil MCP n'écrit sur un topic d'actionneur ; l'écriture passe uniquement par l'arbitre de S1 | `test_catalogue::test_mutation_tools_are_annotated_destructive`, `test_catalogue::test_no_tool_can_write_an_actuator_topic`, `test_catalogue::test_read_only_tools_are_annotated_read_only` |
| `SAF-02` | Les limites effectives (vitesses, bornes de paramètres, actions autorisées) sont appliquées par S1, jamais déléguées … | — **non couverte** |
| `SAF-03` | safety_stop pose un verrou persistant : aucune reprise de mouvement sans action humaine explicite | — **non couverte** |
| `SAF-04` | Le canal MCP est authentifié, en boucle locale, et l'absence de jeton n'ouvre aucun droit | `test_auth_transport::test_error_body_never_leaks_the_expected_token` |
| `SAF-05` | Un incident de sévérité 4 n'autorise que safety_stop et escalate | `test_trigger_firing::test_severity_four_restricts_mutations` |
| `SAF-06` | La perte du canal MCP ne modifie pas le comportement de S1 : la surveillance, le watchdog et les politiques de repris… | — **non couverte** |
| `SAF-07` | Toute mutation est réversible ou explicitement marquée irréversible ; les mutations réversibles enregistrent la valeu… | — **non couverte** |
| `SAF-08` | Le journal d'audit est en ajout seul, avec rotation, et conserve au minimum 30 jours d'incidents | — **non couverte** |
| `TRC-01` | Chaque exigence de ce document porte un identifiant stable référencé par au moins un test | — **non couverte** |
| `TRC-02` | Chaque déclencheur et chaque outil MCP possède un identifiant de spécification cité dans son test | — **non couverte** |
| `TRC-03` | Toute évolution de S1 issue d'une intervention de S2 référence l'incident_id d'origine et l'exigence modifiée | — **non couverte** |
| `TRC-04` | La suite de tests complète est exécutée avant et après chaque évolution de S1 | — **non couverte** |
| `TRC-05` | Le schéma du contexte et le catalogue d'outils sont versionnés ; un changement incompatible incrémente schema_version | — **non couverte** |
| `TRG-01` | Un nœud déclaré critique absent du graphe pendant la fenêtre | `test_trigger_firing::test_catalogue_covers_fourteen_triggers`, `test_trigger_invariants::test_dedup_updates_open_incident_instead_of_creating_a_new_one`, `test_trigger_invariants::test_recovery_policy_resolves_without_calling_system_two` |
| `TRG-A1` | Chaque déclencheur possède un test qui provoque la condition et vérifie la création d'un incident avec le bon trigger… | `test_trigger_firing::test_trigger_fires_with_expected_severity_and_tools` |
| `TRG-02` | Un service ou une action déclarée critique indisponible | — **non couverte** |
| `TRG-A2` | Chaque déclencheur possède un test qui vérifie l'absence d'incident lorsque la condition est sous le seuil | `test_trigger_firing::test_no_trigger_below_threshold` |
| `TRG-03` | Topic critique sans données : âge du dernier message > 3 × période déclarée | `test_context::test_context_contains_every_required_block`, `test_incident_context::test_incident_get_returns_the_context_of_the_specification`, `test_notify::test_anomaly_message_names_the_trigger` |
| `TRG-A3` | TRG-20, TRG-21, TRG-22, TRG-23 et TRG-24 possèdent chacune un test d'invariant | — **non couverte** |
| `TRG-04` | Cadence mesurée d'un topic critique < 50 % de la cadence nominale pendant 5 s | — **non couverte** |
| `TRG-A4` | La latence entre condition vraie et émission de l'incident est inférieure à debounce + 200 ms, mesurée sur 100 occurr… | `test_trigger_latency::test_latency_stays_within_debounce_plus_200ms` |
| `TRG-05` | Incompatibilité QoS confirmée entre un éditeur et un abonné critiques | `test_incident_context::test_incident_get_without_measurement_stays_honest`, `test_trigger_invariants::test_cooldown_blocks_new_incident_and_journals_it`, `test_trigger_invariants::test_rate_limit_caps_incidents_per_hour` |
| `TRG-06` | Transformation TF requise absente ou périmée (> 1 s) | — **non couverte** |
| `TRG-07` | Température d'une zone au-delà du seuil passif (70 °C) | — **non couverte** |
| `TRG-08` | Tension batterie sous le seuil bas (valeur en §10, D-06) | — **non couverte** |
| `TRG-09` | Espace libre de la partition racine sous le seuil (valeur en §10, D-07) | — **non couverte** |
| `TRG-10` | Échec d'un objectif d'action (aborted, canceled, rejeté) non prévu par la politique de reprise | — **non couverte** |
| `TRG-11` | Watchdog d'arrêt déclenché deux fois en 30 s sans commande reçue | `test_trigger_firing::test_severity_four_restricts_mutations` |
| `TRG-12` | Échec répété d'un appel d'outil du pont (même outil, 3 échecs en 60 s) | — **non couverte** |
| `TRG-13` | Exception non gérée dans un nœud S1 (message hors des classes connues) | — **non couverte** |
| `TRG-14` | Condition non modélisée signalée par S1 lui-même (unknown_condition explicite) | `test_trigger_firing::test_catalogue_covers_fourteen_triggers` |
| `TRG-20` | Un incident déjà ouvert sur le même déclencheur et le même sujet ne crée pas de doublon : il incrémente son compteur … | `test_trigger_invariants::test_dedup_updates_open_incident_instead_of_creating_a_new_one` |
| `TRG-21` | Un déclencheur en cooldown ne crée pas d'incident ; l'événement est journalisé avec le motif COOLDOWN | `test_trigger_invariants::test_cooldown_blocks_new_incident_and_journals_it` |
| `TRG-22` | Un incident dont S1 dispose d'une politique de reprise applicable est résolu par S1 sans appel à S2 ; la résolution e… | `test_trigger_invariants::test_recovery_policy_resolves_without_calling_system_two` |
| `TRG-23` | Un incident de sévérité 4 n'ouvre aucun droit d'action autre que safety_stop et escalate | `test_trigger_firing::test_severity_four_restricts_mutations` |
| `TRG-24` | Aucun incident n'est créé hors des déclencheurs déclarés : le jeu TRG-01 à TRG-14 est clos. Ajouter un déclencheur ex… | `test_trigger_firing::test_catalogue_covers_fourteen_triggers`, `test_trigger_invariants::test_undeclared_trigger_is_refused` |

## 3. Exigences sans test

Ces exigences sont écrites mais aucune fonction de test ne les référence.

- `EF-01` — Le service publie la totalité de ses capacités sous forme de schémas JSON conformes au sous-ensemble OpenAI (type, fu… (`llm2ros_bridge_specification.md`)
- `EF-02` — Les schémas sont générés depuis une source unique, partagée avec la validation serveur et la documentation (`llm2ros_bridge_specification.md`)
- `EF-03` — Chaque réponse est un objet JSON structuré {"ok":bool, "data":object, "error":{"code","message"}} (`llm2ros_bridge_specification.md`)
- `EF-04` — Le champ arguments est accepté en objet JSON et en chaîne JSON encodée (`llm2ros_bridge_specification.md`)
- `EF-05` — Les erreurs sont typées par un code stable (E_INVALID_ARG, E_UNKNOWN_TOOL, E_MODE_FORBIDDEN, E_HW_UNREACHABLE, E_TIME… (`llm2ros_bridge_specification.md`)
- `EF-06` — La version sémantique du service est exposée (/health, en-tête) et le code source est versionné (`llm2ros_bridge_specification.md`)
- `EF-07` — Une spécification OpenAPI 3.1 est servie et décrit toutes les routes (`llm2ros_bridge_specification.md`)
- `EF-08` — Chaque requête reçoit un identifiant de corrélation, retourné au client (X-Request-Id et champ request_id) (`llm2ros_bridge_specification.md`)
- `EF-09` — L'identifiant de corrélation est présent dans chaque journal d'exécution, avec outil, arguments normalisés, mode, rés… (`llm2ros_bridge_specification.md`)
- `EF-10` — Les appels d'outils bruts du LLM sont archivés pour audit (horodatage, nom, arguments, réponse) (`llm2ros_bridge_specification.md`)
- `EF-11` — Toute commande de vitesse porte une durée bornée, et l'arrêt effectif survient au plus tard 300 ms après l'échéance (`llm2ros_bridge_specification.md`)
- `EF-12` — Une seule commande de mouvement est active à la fois : les commandes concurrentes sont sérialisées ou rejetées avec u… (`llm2ros_bridge_specification.md`)
- `EF-13` — Stop est prioritaire sur toute autre commande et s'exécute même lorsqu'une action est en cours (`llm2ros_bridge_specification.md`)
- `EF-14` — Le watchdog d'arrêt est indépendant du client HTTP et du processus serveur (`llm2ros_bridge_specification.md`)
- `EF-15` — Les bornes de vitesse ont une source unique de vérité, identique dans le schéma, la validation, le service matériel e… (`llm2ros_bridge_specification.md`)
- `EF-16` — Une commande de navigation n'est acceptée que si ses prérequis sont présents : odométrie, transformation map→odom→bas… (`llm2ros_bridge_specification.md`)
- `EF-17` — La navigation s'appuie sur un contrôleur en boucle fermée (Nav2) ; aucun déplacement en boucle ouverte n'est exposé s… (`llm2ros_bridge_specification.md`)
- `EF-18` — Le référentiel des coordonnées cibles est déclaré et vérifié à l'exécution (`llm2ros_bridge_specification.md`)
- `EF-19` — L'ensemble des caméras disponibles est découvert à l'exécution et publié dans les schémas (énumération) (`llm2ros_bridge_specification.md`)
- `EF-20` — Une capture renvoie le chemin du fichier, les métadonnées (largeur, hauteur, horodatage) et l'image, avec une taille … (`llm2ros_bridge_specification.md`)
- `EF-21` — Une caméra indisponible produit E_CAMERA_UNAVAILABLE avec le périphérique attendu et non une erreur générique (`llm2ros_bridge_specification.md`)
- `EF-22` — La détection d'objets renvoie detection_count, inference_ms et la liste des boîtes au format vision_msgs ou équivalen… (`llm2ros_bridge_specification.md`)
- `EF-23` — Les angles articulaires sont validés en cardinalité, en type et en borne avant tout envoi au matériel (`llm2ros_bridge_specification.md`)
- `EF-24` — Chaque articulation est bornée dans le schéma et dans la validation (`llm2ros_bridge_specification.md`)
- `EF-25` — La pince accepte exactement deux états et retourne l'angle appliqué (`llm2ros_bridge_specification.md`)
- `EF-26` — Une pose nommée est identifiée par un identifiant borné, et son contenu est publié en lecture (`llm2ros_bridge_specification.md`)
- `EF-27` — La synthèse vocale n'exécute aucun interpréteur de commandes : l'argument texte est transmis comme un argument de pro… (`llm2ros_bridge_specification.md`)
- `EF-28` — Le texte de synthèse est borné en longueur (≤ 300 caractères) et normalisé (`llm2ros_bridge_specification.md`)
- `EF-29` — La reconnaissance vocale soit renvoie une transcription, soit retourne E_FEATURE_UNAVAILABLE avec le prérequis manquant (`llm2ros_bridge_specification.md`)
- `EF-30` — Les paramètres de LED et de buzzer sont bornés et validés côté serveur (`llm2ros_bridge_specification.md`)
- `EF-31` — La tension est publiée avec son horodatage et un indicateur de péremption (`llm2ros_bridge_specification.md`)
- `EF-32` — L'état de charge est calculé selon une courbe déclarée et documentée, ou marqué indisponible (`llm2ros_bridge_specification.md`)
- `EF-33` — La télémétrie agrégée (IMU, vitesse, servos, énergie) est exposée au LLM (`llm2ros_bridge_specification.md`)
- `EF-34` — Le mode courant restreint l'ensemble des outils exécutables (`llm2ros_bridge_specification.md`)
- `EF-35` — Le passage de mode exécute ses préconditions (arrêt, position de bras, signalisation) de manière atomique (`llm2ros_bridge_specification.md`)
- `EF-36` — Le mode est persistant et son état initial est explicite au démarrage (`llm2ros_bridge_specification.md`)
- `EF-37` — Les routes d'exploitation et de développement (build, test, maintenance) sont soumises au mode et à l'authentificatio… (`llm2ros_bridge_specification.md`)
- `EF-38` — /health distingue vivacité du processus et disponibilité de la chaîne ROS 2 et du service matériel (`llm2ros_bridge_specification.md`)
- `EF-39` — L'arrêt du service remet les actionneurs en état sûr et publie une vitesse nulle (`llm2ros_bridge_specification.md`)
- `EF-40` — Les fonctions de cartographie (démarrage/arrêt SLAM, sauvegarde, liste, lecture d'image) sont soit exposées avec leur… (`llm2ros_bridge_specification.md`)
- `HLT-11` — La sonde ros initialise un contexte rclpy en lecture seule dans le domaine courant, ne crée aucun éditeur, et le détr… (`llm2ros_health_test_specification.md`)
- `HLT-14` — Le test de santé ne redéfinit aucune règle de déclenchement : il alimente Observation, TriggerEngine décide (`llm2ros_health_test_specification.md`)
- `HLT-16` — Chaque verdict cite l'exigence et l'inventaire qui le justifient (spec_refs) (`llm2ros_health_test_specification.md`)
- `MCP-01` — Le serveur MCP expose le protocole JSON-RPC 2.0 conforme à la révision MCP retenue (D-01), transport HTTP streaming s… (`llm2ros_mcp_specification.md`)
- `MCP-06` — Côté S2, la configuration est /home/jetson/.hermes/config.yaml, clé mcp_servers.clawbot, et les outils apparaissent s… (`llm2ros_mcp_specification.md`)
- `MCP-11` — Toute réponse est un objet JSON {status, data?, error?} avec status ∈ {ok, refused, duplicate, timeout, error} (`llm2ros_mcp_specification.md`)
- `MCP-14` — Les mutations sont sérialisées par l'arbitre d'actionneurs de S1 : au plus une mutation active à la fois (`llm2ros_mcp_specification.md`)
- `MCP-16` — Le délai d'un appel de lecture est inférieur à 2 s ; un appel de mutation est acquitté en moins de 5 s ; test_run dis… (`llm2ros_mcp_specification.md`)
- `MCP-17` — Le débit est limité à 60 appels de lecture par minute et à 10 mutations par minute ; au-delà, MCP-E-BUSY (`llm2ros_mcp_specification.md`)
- `MCP-18` — Chaque appel est journalisé avec incident_id, outil, arguments normalisés, décision de S1, résultat et durée (`llm2ros_mcp_specification.md`)
- `SAF-02` — Les limites effectives (vitesses, bornes de paramètres, actions autorisées) sont appliquées par S1, jamais déléguées … (`llm2ros_mcp_specification.md`)
- `SAF-03` — safety_stop pose un verrou persistant : aucune reprise de mouvement sans action humaine explicite (`llm2ros_mcp_specification.md`)
- `SAF-06` — La perte du canal MCP ne modifie pas le comportement de S1 : la surveillance, le watchdog et les politiques de repris… (`llm2ros_mcp_specification.md`)
- `SAF-07` — Toute mutation est réversible ou explicitement marquée irréversible ; les mutations réversibles enregistrent la valeu… (`llm2ros_mcp_specification.md`)
- `SAF-08` — Le journal d'audit est en ajout seul, avec rotation, et conserve au minimum 30 jours d'incidents (`llm2ros_mcp_specification.md`)
- `TRC-01` — Chaque exigence de ce document porte un identifiant stable référencé par au moins un test (`llm2ros_mcp_specification.md`)
- `TRC-02` — Chaque déclencheur et chaque outil MCP possède un identifiant de spécification cité dans son test (`llm2ros_mcp_specification.md`)
- `TRC-03` — Toute évolution de S1 issue d'une intervention de S2 référence l'incident_id d'origine et l'exigence modifiée (`llm2ros_mcp_specification.md`)
- `TRC-04` — La suite de tests complète est exécutée avant et après chaque évolution de S1 (`llm2ros_mcp_specification.md`)
- `TRC-05` — Le schéma du contexte et le catalogue d'outils sont versionnés ; un changement incompatible incrémente schema_version (`llm2ros_mcp_specification.md`)
- `TRG-02` — Un service ou une action déclarée critique indisponible (`llm2ros_mcp_specification.md`)
- `TRG-A3` — TRG-20, TRG-21, TRG-22, TRG-23 et TRG-24 possèdent chacune un test d'invariant (`llm2ros_mcp_specification.md`)
- `TRG-04` — Cadence mesurée d'un topic critique < 50 % de la cadence nominale pendant 5 s (`llm2ros_mcp_specification.md`)
- `TRG-06` — Transformation TF requise absente ou périmée (> 1 s) (`llm2ros_mcp_specification.md`)
- `TRG-07` — Température d'une zone au-delà du seuil passif (70 °C) (`llm2ros_mcp_specification.md`)
- `TRG-08` — Tension batterie sous le seuil bas (valeur en §10, D-06) (`llm2ros_mcp_specification.md`)
- `TRG-09` — Espace libre de la partition racine sous le seuil (valeur en §10, D-07) (`llm2ros_mcp_specification.md`)
- `TRG-10` — Échec d'un objectif d'action (aborted, canceled, rejeté) non prévu par la politique de reprise (`llm2ros_mcp_specification.md`)
- `TRG-12` — Échec répété d'un appel d'outil du pont (même outil, 3 échecs en 60 s) (`llm2ros_mcp_specification.md`)
- `TRG-13` — Exception non gérée dans un nœud S1 (message hors des classes connues) (`llm2ros_mcp_specification.md`)

## 4. Identifiants cités par les tests mais absents des spécifications

Les identifiants sentinelles (`TRG-99`) sont utilisés volontairement par les tests de jeu clos
et ne sont pas des exigences manquantes.

Aucun : chaque identifiant cité par un test existe dans les spécifications.

## 5. Limites de cette matrice

- La couverture est **textuelle** : un test qui cite `MCP-04` vérifie un point de cette exigence,
  pas nécessairement toute l'exigence. La revue humaine reste nécessaire.
- Les exigences des documents historiques (`llm2ros_bridge_specification.md`) sont incluses ;
  elles décrivent le pont C++ en service, pas le pont MCP en construction.
- Les fichiers de test hors `tests/mcp_bridge` ne sont pas analysés.

## 6. Voir aussi

- [[llm2ros_mcp_specification]] — spécification de l'interface MCP et des déclencheurs
- [[llm2ros_mcp_test_plan]] — architecture de la suite de tests
- [[llm2ros_health_test_specification]] — exigences HLT
- [[llm2ros_bridge_design]] — conception détaillée des modules
