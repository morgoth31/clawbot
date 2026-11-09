---
title: "Index — Robot Knowledge Base (Clawbot X3 / Jetson Orin NX)"
date: "2026-11-10T06:14:09+08:00"
author: "Hermes Agent"
tags: [index, okf, ros2, jetson, clawbot, knowledge-base]
status: actif
---

# Index — Robot Knowledge Base

Document racine du graphe de connaissances du robot mobile autonome **Clawbot X3** (hôte `yahboom`, Jetson Orin NX, ROS 2 Humble). Chaque rapport est un fichier Markdown à en-tête OKF, relié aux autres par des liens wiki bidirectionnels (nom du fichier entre doubles crochets).

## 1. Synthèse de la plateforme

| Sous-système | Référence matérielle / logicielle | Document |
|---|---|---|
| Calcul embarqué | NVIDIA Jetson Orin NX 16 Go, L4T R36.4.7, Ubuntu 22.04.5 | [[jetson_orin_nx]] |
| Carte de commande bas niveau | Carte Rosmaster (Yahboom), lien série UART 115 200 Bd | [[rosmaster_x3_mcu]] |
| Perception RGB-D | Orbbec Astra Pro+ (USB `2bc5:060f`) | [[orbbec_astra_pro_plus]] |
| Énergie | Batterie principale, tension télémétrée 11,9 V | [[batterie_principale]] |
| Middleware | ROS 2 Humble, `ROS_DOMAIN_ID=28` | [[ros2_graph_clawbot]] |
| Nœud de conduite | `Mcnamu_driver_X3` (`yahboomcar_bringup`) | [[yahboomcar_bringup_driver_node]] |
| Pont LLM → ROS 2 | `api_server` (C++, 8000) + `hardware_service` (Python, 8001), 18 outils | [[llm2ros_bridge]] |
| Supervision système | 8 unités systemd actives + 2 conteneurs Docker | [[systemd_robot_services]] |

## 2. Arborescence normalisée

```
/Robot_Knowledge_Base/
├── index.md
├── 01_Hardware/
│   ├── jetson_orin_nx.md
│   ├── rosmaster_x3_mcu.md
│   ├── orbbec_astra_pro_plus.md
│   └── batterie_principale.md
├── 02_Software/
│   ├── ros2_graph_clawbot.md
│   ├── yahboomcar_bringup_driver_node.md
│   ├── systemd_robot_services.md
│   ├── ros2_nav_stack.md
│   ├── llm2ros_bridge.md
│   ├── llm2ros_bridge_architecture.md
│   ├── llm2ros_bridge_specification.md
│   ├── llm2ros_bridge_coherence_et_approche.md
│   ├── llm2ros_mcp_specification.md
│   ├── llm2ros_mcp_test_plan.md
│   ├── ros2_engineering_skills.md
│   ├── acsl_frama_c_skills.md
│   └── mattpocock_engineering_skills.md
└── 03_Operations/
    ├── 2026-11-10_bootstrap_knowledge_base.md
    └── errors_traces/
        ├── ERR-2026-11-10-001_absence_topic_scan.md
        ├── ERR-2026-11-10-002_espace_disque_critique.md
        ├── ERR-2026-11-10-003_arbre_tf_incomplet.md
        └── ERR-2026-11-10-004_execution_de_commande_non_authentifiee.md
```

## 3. Conventions d'écriture

- En-tête YAML obligatoire : `title`, `date` (ISO 8601 avec fuseau), `author` (« Hermes Agent »), `tags`, `status`.
- Valeurs de `status` : `actif` (document vivant), `validé` (état constaté et horodaté), `ouvert` (anomalie non close), `obsolète`.
- Toute mesure porte sa source (topic ROS 2, fichier sysfs, sortie de commande) et l'horodatage de capture.
- Toute donnée absente est écrite « Donnée non disponible », suivie du code d'erreur ou de la commande qui l'établit.
- Aucune appréciation qualitative : uniquement des valeurs mesurées, des chemins et des codes de retour.

## 4. Journal des opérations

| Date (CST) | Événement | Document |
|---|---|---|
| 2026-11-10 06:11 | Création de la base et capture de l'état initial des sous-systèmes | [[2026-11-10_bootstrap_knowledge_base]] |
| 2026-11-10 06:12 | Anomalie ouverte : aucune source de scan laser publiée sur le domaine 28 | [[ERR-2026-11-10-001_absence_topic_scan]] |
| 2026-11-10 06:12 | Anomalie ouverte : partition racine à 97 % d'occupation (4,3 Go libres) | [[ERR-2026-11-10-002_espace_disque_critique]] |
| 2026-11-10 06:14 | Anomalie ouverte : arbre TF sans `base_link`, sans `odom`, sans `map` | [[ERR-2026-11-10-003_arbre_tf_incomplet]] |
| 2026-11-10 06:21 | Anomalie critique ouverte : exécution de commande arbitraire sans authentification sur le pont LLM | [[ERR-2026-11-10-004_execution_de_commande_non_authentifiee]] |
| 2026-11-10 06:53 | Installation du skill `ros2-engineering-skills` (28 références, 15 validateurs) et ajout du menu Skills au site | [[ros2_engineering_skills]] |
| 2026-11-10 07:00 | Installation des 5 skills ACSL / Frama-C (`acsl-verify`, `acsl-spec`, `frama-c-wp`, `verifiable-c`, `wp-coq`) | [[acsl_frama_c_skills]] |
| 2026-11-10 07:24 | Installation des 27 skills `mattpocock/skills` (20 ingénierie système + 7 productivité) | [[mattpocock_engineering_skills]] |
| 2026-11-10 07:35 | Étape 1 du projet MCP : spécification des exigences S1/S2 (interface, déclencheurs, contexte) | [[llm2ros_mcp_specification]] |
| 2026-11-10 07:45 | Étape 2 du projet MCP : architecture de la suite de tests, isolation, traçabilité | [[llm2ros_mcp_test_plan]] |
| 2026-11-10 07:52 | Étape 3 du projet MCP : squelettes de tests MCP livrés, 1 vert / 22 rouges attendus | [[llm2ros_mcp_test_plan]] |
| 2026-11-10 08:15 | Étape 4 du projet MCP : serveur MCP implémenté, 23/23 tests de contrat verts | [[llm2ros_mcp_test_plan]] |
