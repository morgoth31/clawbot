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
| Sortie audio | Sony SRS-XB100, A2DP appairée le 2026-11-11 (contournement HCI) | [[srs_xb100]] |
| Perception RGB-D | Orbbec Astra Pro+ (USB `2bc5:060f` profondeur, `2bc5:050f` couleur, hors V4L) | [[orbbec_astra_pro_plus]] |
| Caméra du bras | Module UVC `0c45:6340` sur le port `1-2.2.1`, aucun topic ROS publié | [[camera_usb_bras]] |
| Perception laser | YDLIDAR TG30, TOF 360°, firmware 1.71, `/scan` à 10,05 Hz | [[ydlidar_tg30]] |
| Bras manipulateur | 5 axes + pince, 6 servos bus série sur le MCU, présence confirmée le 2026-11-10 | [[bras_6dof]] |
| Manipulation | MoveIt 2.5.10 + `clawbot_moveit_config` + `clawbot_arm_controller`, plan et exécution mesurés | [[manipulation_moveit]] |
| Description géométrique | `clawbot_x3plus.urdf`, 21 liens, `clawbot-description.service` | [[modele_urdf_clawbot]] |
| Énergie | Batterie principale, tension télémétrée 11,9 V | [[batterie_principale]] |
| Middleware | ROS 2 Humble, `ROS_DOMAIN_ID=28` | [[ros2_graph_clawbot]] |
| Nœud de conduite | `Mcnamu_driver_X3` (`yahboomcar_bringup`) | [[yahboomcar_bringup_driver_node]] |
| Pont LLM → ROS 2 | `api_server` (C++, 8000) + `hardware_service` (Python, 8001), 18 outils | [[llm2ros_bridge]] |
| Supervision système | 8 unités systemd actives + 2 conteneurs Docker | [[systemd_robot_services]] |
| Directeur S1 (exécution) | `clawbot_director`, service `/director/command`, 25 outils MCP | [[directeur_s1]] |
| Sentinel S1 (attention) | `clawbot_sentinel`, YOLO + profondeur, mots d'arrêt, réveil S2 | [[sentinel_s1]] |
| Navigation sur carte | Nav2 (`clawbot-nav2.service`) + AMCL, catalogue fermé de 3 waypoints | [[navigation_nav2_waypoints]] |
| Préconditions de mouvement | bras replié mesuré avant tout skill qui déplace la base | [[preconditions_mouvement]] |

## 2. Arborescence normalisée

```
/Robot_Knowledge_Base/
├── index.md
├── 01_Hardware/
│   ├── jetson_orin_nx.md
│   ├── rosmaster_x3_mcu.md
│   ├── ydlidar_tg30.md
│   ├── orbbec_astra_pro_plus.md
│   ├── bras_6dof.md
│   ├── camera_usb_bras.md
│   ├── inventaire_materiel.md
│   ├── srs_xb100.md
│   └── batterie_principale.md
├── 02_Software/
│   ├── documentation_constructeur_yahboom.md
│   ├── ros2_graph_clawbot.md
│   ├── yahboomcar_bringup_driver_node.md
│   ├── systemd_robot_services.md
│   ├── ros2_nav_stack.md
│   ├── modele_urdf_clawbot.md
│   ├── manipulation_moveit.md
│   ├── mcp_hermes.md
│   ├── etalonnage_bras.md
│   ├── ports_reseau.md
│   ├── bom_logiciel.md
│   ├── llm2ros_bridge.md
│   ├── llm2ros_bridge_architecture.md
│   ├── llm2ros_bridge_specification.md
│   ├── llm2ros_bridge_coherence_et_approche.md
│   ├── llm2ros_bridge_design.md
│   ├── llm2ros_mcp_specification.md
│   ├── llm2ros_mcp_test_plan.md
│   ├── llm2ros_traceabilite.md
│   ├── llm2ros_health_test_specification.md
│   ├── ros2_engineering_skills.md
│   ├── acsl_frama_c_skills.md
│   └── mattpocock_engineering_skills.md
└── 03_Operations/
    ├── 2026-11-10_bootstrap_knowledge_base.md
    ├── 2026-11-10_tests_cartographie.md
    ├── 2026-11-10_rebranchement_camera_bras.md
    ├── 2026-11-10_mise_en_service_manipulation.md
    ├── etat_noeuds_et_services.md
    ├── mise_a_jour_firmware_carte_rosmaster.md
    └── errors_traces/
        ├── ERR-2026-11-10-001_absence_topic_scan.md
        ├── ERR-2026-11-10-002_espace_disque_critique.md
        ├── ERR-2026-11-10-003_arbre_tf_incomplet.md
        ├── ERR-2026-11-10-004_execution_de_commande_non_authentifiee.md
        ├── ERR-2026-11-10-005_pytest_plugins_launch_testing.md
        ├── ERR-2026-11-10-006_horloge_fuseau_et_ntp.md
        ├── ERR-2026-11-10-007_retour_angle_servo_bras.md
        ├── ERR-2026-11-10-008_paquet_opencv_incomplet.md
        └── ERR-2026-11-10-009_commande_vitesse_non_proportionnelle.md
```

## 3. Conventions d'écriture

- En-tête YAML obligatoire : `title`, `date` (ISO 8601 avec fuseau), `author` (« Hermes Agent »), `tags`, `status`.
- Valeurs de `status` : `actif` (document vivant), `validé` (état constaté et horodaté), `ouvert` (anomalie non close), `obsolète`.
- Toute mesure porte sa source (topic ROS 2, fichier sysfs, sortie de commande) et l'horodatage de capture.
- Toute donnée absente est écrite « Donnée non disponible », suivie du code d'erreur ou de la commande qui l'établit.
- Aucune appréciation qualitative : uniquement des valeurs mesurées, des chemins et des codes de retour.

## 4. Journal des opérations

| Date (fuseau du poste, `+01:00` depuis le 2026-11-10 06:55) | Événement | Document |
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
| 2026-11-10 08:32 | Étape 5 du projet MCP : 14 déclencheurs et contexte §6 implémentés, 70/70 tests verts | [[llm2ros_mcp_test_plan]] |
| 2026-11-10 08:44 | pytest interrompu par les plugins `launch_testing` de ROS 2 Humble : contournement et trace | [[ERR-2026-11-10-005_pytest_plugins_launch_testing]] |
| 2026-11-10 08:12 | Test de santé des périphériques : spécification HLT proposée (18 exigences, 4 décisions ouvertes) | [[llm2ros_health_test_specification]] |
| 2026-11-10 08:26 | Test de santé implémenté : 33 tests, rapport réel sur le robot, service systemd au démarrage | [[llm2ros_health_test_specification]] |
| 2026-11-10 13:40 | Documentation réorganisée en cinq sections ; pages générées de traçabilité, d'état des nœuds et de BOM ; conception détaillée du pont | [[llm2ros_bridge_design]], [[llm2ros_traceabilite]], [[etat_noeuds_et_services]], [[bom_logiciel]] |
| 2026-11-10 13:55 | Lidar : ERR-001 corrigée — YDLIDAR TG30 présent, pilote jamais lancé ; `clawbot-lidar.service` déployé, `/scan` à 10,15 Hz | [[ERR-2026-11-10-001_absence_topic_scan]], [[etat_noeuds_et_services]] |
| 2026-11-10 06:55 | Horloge : fuseau passé de `Asia/Shanghai` à `Europe/Paris`, RTC en UTC, NTP français ; UTC était déjà exact | [[ERR-2026-11-10-006_horloge_fuseau_et_ntp]] |
| 2026-11-10 18:16 | Lidar TG30 documenté sur le poste : identification, paramètres, QoS `BEST_EFFORT`, écart avec la référence `TG.launch` | [[ydlidar_tg30]] |
| 2026-11-10 18:25 | Carte Rosmaster : inventaire de la V3.0 et protocole série bas niveau extraits de la documentation constructeur, procédure de flashage transcrite | [[rosmaster_x3_mcu]], [[mise_a_jour_firmware_carte_rosmaster]] |
| 2026-11-10 18:33 | Dépôt constructeur `ROSMASTERX3-PLUS` référencé : structure, applicabilité à ROS 2 Humble, règles de citation | [[documentation_constructeur_yahboom]] |
| 2026-11-10 18:35 | Caméra Astra : modes UVC mesurés, état d'étalonnage, conflit de port 8080 avec `web_video_server`, rattachement TF `base_link` corrigé | [[orbbec_astra_pro_plus]] |
| 2026-11-10 19:00 | Bras 6 axes : présence confirmée, angles lus sur la carte, servo 4 au retour invalide, double éditeur de `/joint_states` | [[bras_6dof]], [[ERR-2026-11-10-007_retour_angle_servo_bras]] |
| 2026-11-10 19:05 | URDF : `laser_link` remplacé par un cylindre TG30 (Ø 75,8 × 34,7 mm, 214 g), modèle revalidé, TF inchangé | [[modele_urdf_clawbot]] |
| 2026-11-10 19:07 | Acquisition IMU corrigée : attitude de la trame `0x0C` publiée en quaternion ; reconstruction propre du workspace, 19 paquets verts | [[yahboomcar_bringup_driver_node]] |
| 2026-11-10 19:10 | Stockage : partition ramenée de 97 % à 85 % (22 Go libres), ERR-002 clôturée | [[ERR-2026-11-10-002_espace_disque_critique]] |
| 2026-11-10 19:15 | Ports réseau : allocation consignée, `web_video_server` déplacé sur 8082, site conservé sur 8080 | [[ports_reseau]] |
| 2026-11-10 19:25 | SLAM : `yahboomcar_slam` recompile contre OpenCV 4.5.4 (préfixe `/opt/opencv-4.5.4-dev`), paquet NVIDIA 4.8 incomplet tracé, état des prérequis de navigation remis à jour | [[ERR-2026-11-10-008_paquet_opencv_incomplet]], [[ros2_nav_stack]] |
| 2026-11-10 20:35 | Cartographie : deux essais sur le robot (statique puis roues en l'air), cartes sauvegardées dans `maps/`, `/map` à 1 Hz | [[2026-11-10_tests_cartographie]] |
| 2026-11-10 20:40 | Anomalie critique : boucle de vitesse saturée (~0,82 m/s) et signe inversé quelle que soit la consigne ; cartographie réelle impossible sur cales | [[ERR-2026-11-10-009_commande_vitesse_non_proportionnelle]] |
| 2026-11-10 19:16 | Caméra du bras débranchée puis rebranchée : reprise UVC sur `video0` (device 6 → 16), capture V4L2 et inférence OpenCV OK ; index « claw » toujours sur 2, outil non fonctionnel ; identification de la caméra du bras séparée de l'Astra | [[2026-11-10_rebranchement_camera_bras]], [[camera_usb_bras]] |
| 2026-11-10 19:55 | Manipulation : MoveIt 2 planifie et exécute jusqu'aux servos — paquets `clawbot_moveit_config` et `clawbot_arm_controller`, 22 tests verts, plan à 30 points, chaîne complète validée sur domaine isolé ; index caméra « claw » ramené à 0 (HTTP 200) | [[2026-11-10_mise_en_service_manipulation]], [[manipulation_moveit]] |
| 2026-11-10 23:05 | Essais physiques du bras : les six servos commandés et relus (±1°), servo 4 réparé par rebranchement (ERR-007 close), axe 4 réintégré ; cascade systemd et instantané de pose documentés | [[manipulation_moveit]], [[ERR-2026-11-10-007_retour_angle_servo_bras]] |
| 2026-11-10 23:20 | Collisions du bras avec le mât : MoveIt déclare valide la configuration qui a bloqué le bras — les zéros servo sont une convention ; procédure d'étalonnage et outil de contrôle livrés | [[etalonnage_bras]], [[manipulation_moveit]] |
| 2026-11-10 23:38 | Support caméra ajouté au modèle de collision (boîte + marge 2 cm) : la pose qui bloquait est refusée ; balayage de `q4` sans l'objet → aucune collision, avec l'objet → toutes, ce qui écarte l'hypothèse du seul défaut du servo 4 | [[etalonnage_bras]] |
| 2026-11-10 23:55 | Approche physique du mât : premier contact à servo2 ≈ 114° (caméra USB, `mono_link`), refus du modèle dès 105-106° — soit 8-9° de marge ; plan vers la zone de contact refusé | [[etalonnage_bras]] |
| 2026-11-11 00:18 | Inventaire matériel mesuré (14 lignes : présence, fonction, nœud ROS 2) et serveur MCP câblé sur ROS 2 puis enregistré dans Hermes en stdio (22 outils, graph_snapshot et topic_stats vérifiés) | [[inventaire_materiel]], [[mcp_hermes]] |
| 2026-11-11 00:30 | Déclenchement S1 → Hermes : voie `cli` vérifiée (46,4 s, réponse sourcée), route webhook `clawbot-incident` créée, activation par redémarrage de la passerelle en attente | [[mcp_hermes]] §4 |
| 2026-11-11 08:40 | ERR-010 ouverte : base non proportionnelle documentée — signe inversé mesuré sur cales (corrigé), temps mort 1,2 s, gain 1,64, pics 5,6x, saturation 1,29 ; type de châssis et PID à lire depuis le driver | [[ERR-2026-11-11-010_base_non_proportionnelle]] |
| 2026-11-11 12:00 | SLAM réparé : `base_frame` valait `base_footprint` (inexistante), tous les scans rejetés ; carte 8,1 × 6,5 m obtenue, `map→odom` recale 24 cm sur 2,6 m | [[slam_cartographie]] |
| 2026-11-11 14:10 | Directeur S1 branché : nœud `clawbot-director`, service `/director/command`, exécution d'un goal par étape, annulation sécurité 1,90 ms, 3 outils MCP (25 au catalogue), 212 tests verts ; skills physiques encore indisponibles | [[directeur_s1]] |
| 2026-11-11 16:45 | Enceinte appairée : contournement HCI (`IO_Capability_Request_Reply` injecté), clé stockée, sortie A2DP active et testée au son ; procédure conservée dans `scripts/appairer_enceinte_bluetooth.sh` | [[srs_xb100]], [[ERR-2026-11-11-011_bluetooth_appairage_sans_ble]] |
| 2026-11-11 16:05 | Compte rendu de reprise sur l'appairage Bluetooth : configuration mesurée, modifications, preuves HCI, hypothèses éliminées et pistes classées par coût | [[2026-11-11_compte_rendu_bluetooth_srs_xb100]] |
| 2026-11-11 15:20 | Bluetooth : appairage de la SRS-XB100 impossible — noyau sans BLE (`CONFIG_BT_LE` absent), profils audio NVIDIA désactivés et module PulseAudio manquant corrigés ; trace ouverte | [[ERR-2026-11-11-011_bluetooth_appairage_sans_ble]] |
| 2026-11-11 14:20 | Sentinel S1 déployé : machine d'attention (2 frames, 0,75 / 3,5 m, cooldowns 60 s et 5 s), mots d'arrêt locaux, réveil de fin de tâche anti-rebondi ; 236 tests verts, `depth_available` vrai ; VAD et repli Telegram absents | [[sentinel_s1]] |
| 2026-11-11 13:00 | Lot 2 : proprioception `/arm/servo_angles` à 10 Hz sans casser l'EKF, seuils purs (8/12°, 15 cm, 10,5 V), arbitre 20 Hz validé (obstacle 47 ms, chien de garde) | [[systeme1_arbitre]] |
| 2026-11-11 16:41 | Préconditions de mouvement : `navigate_to` exige désormais un bras **mesuré** dans son enveloppe de repos (refus si angles périmés ou jamais reçus), `ExecStop` du directeur annule la tâche en vol, absences du contexte MCP dérivées de l'observation ; 293 tests verts | [[preconditions_mouvement]] |
| 2026-11-11 16:17 | Lot 5 : navigation sur carte — catalogue de waypoints fermé (`ouest`, `centre`, `est`), `navigate_to` devient un adaptateur `NavigateToPose`, EKF et Nav2 en unités persistantes ; 3 waypoints atteints à 0,000 / 0,121 / 0,082 m en simulation, 268 tests verts | [[navigation_nav2_waypoints]] |
