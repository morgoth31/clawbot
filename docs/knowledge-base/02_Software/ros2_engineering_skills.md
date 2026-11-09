---
title: "ros2-engineering-skills — skill et validateurs ROS 2 installés"
date: "2026-11-10T06:53:00+08:00"
author: "Hermes Agent"
tags: [software, ros2, skills, agent, validation, qos, launch]
status: validé
---

# ros2-engineering-skills — skill et validateurs ROS 2

Skill d'ingénierie ROS 2 installé pour l'agent, avec 28 références techniques et 15 utilitaires
exécutables. Retour à l'[[index]]. Contexte : [[ros2_graph_clawbot]], [[llm2ros_bridge]].

## 1. Identification

| Élément | Valeur |
|---|---|
| Dépôt | `https://github.com/dbwls99706/ros2-engineering-skills` |
| Version | 1.7.2 (`metadata.version` du `SKILL.md`) |
| Commit installé | `f0de84d` (`git ls-remote` au 2026-11-10 06:47 CST) |
| Licence | Apache-2.0 |
| Taille | 2,8 Mo (références, scripts, tests, évaluations) |
| Emplacement | `~/.hermes/skills/robotics/ros2-engineering-skills/` |
| Méthode | `./install.sh --target ~/.hermes/skills/robotics/ros2-engineering-skills` (copie, pas de lien symbolique) |
| Nom exposé à l'agent | `ros2-engineering-skills` (catégorie `robotics`) |
| Champs lus par Hermes | `name`, `description` ; 28 références et 15 scripts listés comme fichiers liés |

Le skill est chargé à la demande par l'agent (`skill_view("ros2-engineering-skills")`), puis par
section (`skill_view("ros2-engineering-skills", "references/navigation.md")`).

## 2. Contrat d'usage imposé par le skill

Le corps du `SKILL.md` (192 lignes) définit un contrat en sept points : cadrer le périmètre avant
d'agir, résoudre l'environnement (`ROS_DISTRO`, workspace) avant toute affirmation de version,
diagnostiquer avant de modifier, traiter les seuils et verrous comme des décisions traçables,
vérifier au niveau adapté au risque, séparer incertitude d'ingénierie et décision d'opérateur,
distinguer permission et preuve. Il impose aussi une règle directement applicable ici : une
publication de vitesse nulle ne prouve pas l'arrêt physique de l'actionneur (voir
[[ERR-2026-11-10-004_execution_de_commande_non_authentifiee]] pour un cas voisin de preuve
manquante).

## 3. Références (28)

| Thème | Référence |
|---|---|
| Build et espace de travail | `workspace-build.md` |
| Nœuds et exécuteurs | `nodes-executors.md` |
| Topics, services, actions, QoS/DDS | `communication.md` |
| Cycle de vie et composition | `lifecycle-components.md` |
| Fichiers de lancement | `launch-system.md` |
| tf2 et URDF | `tf2-urdf.md` |
| `ros2_control` | `hardware-interface.md` |
| Temps réel | `realtime.md` |
| Nav2, SLAM, costmaps | `navigation.md` |
| MoveIt 2 | `manipulation.md` |
| Perception (caméra, LiDAR, PCL) | `perception.md` |
| Intégration capteurs | `sensor-integration.md` |
| Tests, `launch_testing`, CI | `testing.md` |
| Progression de preuve | `evidence-progression.md` |
| Débogage, profilage, rosbag2 | `debugging.md` |
| Provenance d'exécution | `runtime-provenance.md` |
| Lignage d'artefacts (cartes, bags) | `artifact-lineage.md` |
| Diagnostics système | `system-diagnostics.md` |
| Déploiement, Docker, OTA | `deployment.md` |
| Bringup, udev, watchdogs | `system-bringup.md` |
| Simulation | `simulation.md` |
| Sécurité SROS2 | `security.md` |
| Arrêt d'urgence | `safety-estop.md` |
| micro-ROS | `micro-ros.md` |
| Multi-robot | `multi-robot.md` |
| Types de messages | `message-types.md` |
| Migration ROS 1 | `migration-ros1.md` |
| Principes transverses | `engineering-principles.md` |

## 4. Outils (15 scripts)

| Script | Rôle | Exécution réelle sur ce robot |
|---|---|---|
| `qos_audit.py` | Audit statique des déclarations QoS d'un paquet | `yahboomcar_bringup` : 0 incompatibilité confirmée, 1 point non résolu, code 0 |
| `qos_checker.py` | Comparaison d'un profil éditeur / abonné, 7 préréglages | `--help` vérifié |
| `launch_validator.py` | Analyse statique de fichiers `*.launch.py` | `slam_launch.py` : aucun problème ; `bridge_launch.py` : 2 avertissements |
| `launch_supervisor.py` | Exécution d'un launch autorisé avec gestion de SIGINT | `--help` vérifié, non exécuté (démarre des processus réels) |
| `rosbag2_qos_checker.py` | Compatibilité QoS d'une relecture de bag | `--help` vérifié, aucun bag présent sur le disque |
| `create_package.py` | Génération de paquets (`cpp`, `python`, `interfaces`, `hardware_interface`) | `--help` vérifié |
| `validate_skill.py` | Contrôles de packaging du skill | `--installed` : `status: pass`, 192 lignes, 38 fichiers référencés |
| `measure_context.py` | Mesure en jetons du corps du skill | nécessite `tiktoken` (non installé) |
| `skill_validate_hook.py` | Inspection d'une commande ou édition proposée | hook client, non branché sous Hermes |
| `skill_stop_hook.py` | Revue des constats d'espace de travail en fin de tâche | idem |
| `claude_hook.py` | Passerelle des hooks Claude Code | inactif sous Hermes (voir §6) |
| `benchmark_capture.py`, `eval_runner.py`, `verify_eval_capture.py`, `install_skill.py` | Harnais d'évaluation et d'installation du dépôt | hors usage courant |

### 4.1 Résultats obtenus sur le code du robot

Audit QoS du paquet de conduite :

```
$ python3 scripts/qos_audit.py /home/jetson/clawbot/yahboomcar_bringup
Summary: confirmed_incompatible=0, confirmed_indeterminate=0, confirmed_compatible=0,
         potential_pairs=0, not_evaluated_pairs=0, confirmed_type_conflicts=0,
         possible_type_conflicts=0, unresolved_endpoints=1, incomplete_files=0
Unresolved endpoints (not inferred):
  subscription at yahboomcar_bringup/patrol_4ROS_R2.py:61: QoS: unrecognized QoS expression self.qos_profile
Exit: 0
```

Validation du fichier de lancement du pont LLM :

```
$ python3 scripts/launch_validator.py /home/jetson/clawbot/ros2_llm_bridge_cpp/launch
Checked 1 launch file(s)
  [WARNING] bridge_launch.py:9: DeclareLaunchArgument 'port' has no 'description'.
  [WARNING] bridge_launch.py:10: DeclareLaunchArgument 'hw_url' has no 'description'.
Found: 0 error(s), 2 warning(s), 0 info(s)
```

Les deux avertissements constituent un constat exploitable pour [[llm2ros_bridge]] : les arguments
de lancement `port` et `hw_url` n'ont pas de description, donc `--show-args` n'expose pas leur
signification à l'exploitant.

## 5. Vérification de l'installation

| Contrôle | Résultat |
|---|---|
| Découverte par Hermes | `skills_list(category="robotics")` liste `ros2-engineering-skills` |
| Chargement du corps | `skill_view("ros2-engineering-skills")` : 192 lignes, 28 références, 15 scripts |
| Validation de packaging | `validate_skill.py --installed` : `status: pass`, 0 erreur, 0 avertissement |
| Suite de tests du dépôt | 1 819 réussis, 1 ignoré, 1 échec (voir ci-dessous) |
| Bibliothèque YAML | PyYAML 6.0.2 présente pour Python 3.10 |

Échec isolé : `tests/test_generated_hardware_api_paths.py::test_probe_wiring_records_the_cache_contract[fails]`.
Le test généré exécute un `try_compile` CMake contre `rclcpp` (`/opt/ros/humble/share/rclcpp/cmake/rclcppConfig.cmake:41`) ;
la configuration échoue dans l'environnement du test, y compris après `source /opt/ros/humble/setup.bash`.
Ce test dépend de l'environnement de compilation, pas de l'intégration Hermes.

Contournement nécessaire à l'exécution des tests : ce poste contient un paquet Python `scripts`
résiduel dans `~/.local/lib/python3.10/site-packages/` (sans `dist-info`). Les tests importent
`from scripts import ...` et résolvent donc ce paquet au lieu du dossier local. Ajout d'un
`scripts/__init__.py` vide dans la copie installée, puis exécution avec `PYTHONPATH=$PWD`. Le
fichier n'existe pas en amont : il est propre à cette installation.

## 6. Hooks Claude non applicables

Le dépôt fournit `hooks/hooks.json` (PreToolUse sur `Edit|Write|Bash`, et Stop) exécutant
`scripts/claude_hook.py` avec `${CLAUDE_PLUGIN_ROOT}`. Ces hooks sont propres à Claude Code :
aucune unité Hermes ne les charge et le skill ne déclare pas de hook Hermes. Sous Hermes, la
validation reste manuelle, par appel explicite des scripts listés en §4.

## 7. Limites

| Limite | Conséquence |
|---|---|
| Validateurs statiques | `qos_audit.py` ne voit ni les remaps, ni les surcharges YAML, ni les défauts RMW ; la confirmation exige `ros2 topic info -v` |
| Aucune exécution matérielle | `launch_supervisor.py` démarre des processus réels ; son usage relève de l'autorisation d'exploitation |
| Évaluations du dépôt | Les captures d'évaluation sont des fixtures, pas une mesure de qualité sur ce robot |
| Connaissance multi-distribution | Le skill décrit Humble, Iron, Jazzy, Kilted ; la version en service ici est Humble, seule à faire foi |

## 8. Voir aussi

- Inventaire des skills de l'agent : `docs/skills/index.md` du dépôt, publié sur le site (menu **Skills**)
- Graphe ROS 2 et nœuds : [[ros2_graph_clawbot]]
- Pont LLM audité : [[llm2ros_bridge]], [[llm2ros_bridge_architecture]]
- Conventions de documentation : [[index]]
