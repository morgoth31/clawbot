---
title: "ros2-engineering-skills — skill et validateurs ROS 2 installés"
date: "2026-11-10T06:53:00+08:00"
author: "Hermes Agent"
tags: [software, ros2, skills, agent, validation, qos, launch]
status: validé
---

# ros2-engineering-skills — skill et validateurs ROS 2

Skill d'ingénierie ROS 2 installé pour l'agent, avec 31 références techniques et 15 utilitaires
exécutables. Retour à l'[[index]]. Contexte : [[ros2_graph_clawbot]], [[llm2ros_bridge]].

## 1. Identification

| Élément | Valeur |
|---|---|
| Dépôt | `https://github.com/dbwls99706/ros2-engineering-skills` |
| Version | 1.8.0 (`metadata.version` du `SKILL.md`) |
| Commit installé | `ee3e486` (`git ls-remote refs/heads/main` au 2026-11-12 01:18 CET) |
| Licence | Apache-2.0 |
| Taille | 3,0 Mo (références, scripts, tests, évaluations ; sans `.git`) |
| Emplacement | `~/.hermes/skills/robotics/ros2-engineering-skills/` |
| Méthode | copie `rsync` de l'arbre 1.8.0 (sans `.git`), puis réapplication des fichiers adaptés localement (§3.1) |
| Nom exposé à l'agent | `ros2-engineering-skills` (catégorie `robotics`) |
| Champs lus par Hermes | `name`, `description` ; 31 références et 16 fichiers de `scripts/` listés comme fichiers liés |

Le skill est chargé à la demande par l'agent (`skill_view("ros2-engineering-skills")`), puis par
section (`skill_view("ros2-engineering-skills", "references/navigation.md")`).

## 2. Contrat d'usage imposé par le skill

Le corps du `SKILL.md` (179 lignes, 11 609 octets pour un budget de 12 000) définit un contrat en sept points : cadrer le périmètre avant
d'agir, résoudre l'environnement (`ROS_DISTRO`, workspace) avant toute affirmation de version,
diagnostiquer avant de modifier, traiter les seuils et verrous comme des décisions traçables,
vérifier au niveau adapté au risque, séparer incertitude d'ingénierie et décision d'opérateur,
distinguer permission et preuve. Il impose aussi une règle directement applicable ici : une
publication de vitesse nulle ne prouve pas l'arrêt physique de l'actionneur (voir
[[ERR-2026-11-10-004_execution_de_commande_non_authentifiee]] pour un cas voisin de preuve
manquante).

## 3. Références (31)

L'amont 1.8.0 conserve les 28 mêmes références qu'en 1.7.2 ; trois références locales s'y ajoutent
(§3.1). Les fichiers `manipulation.md`, `navigation.md`, `safety-estop.md`, `system-bringup.md` et
`testing.md` de la copie installée portent en outre des compléments locaux : l'amont ne les a pas
modifiés entre 1.7.2 et 1.8.0, la version enrichie a donc été conservée telle quelle.

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
| Scripts commandant un mouvement réel | `robot-motion-test-scripts.md` (local) |
| Odométrie/EKF, calibration signe/gain | `odometry-fusion.md` (local) |
| Leçons de terrain (watchdogs, unités, preuve d'arrêt) | `field-lessons.md` (local) |

### 3.1 Références et compléments locaux

| Fichier | Contenu local | Provenance |
|---|---|---|
| `references/odometry-fusion.md` | `/odom` + TF `odom → base_link` sur base Mecanum à MCU série, EKF `robot_localization`, calibration signe/gain, relecture servo dans un budget de boucle à 10 Hz | écrit sur ce poste, 2026-11-11 |
| `references/robot-motion-test-scripts.md` | Règles des scripts qui commandent un mouvement réel (dérive, proportionnalité, cartographie) | écrit sur ce poste, 2026-11-11 |
| `references/field-lessons.md` | Douze leçons de terrain : deux tentatives identiques, silence d'un topic d'état, copie du paquet dans un autre espace, `pkill` sur son propre shell, unité systemd en root, watchdog de commande, état de sécurité périmé, preuve d'arrêt, temps opérateur, signe/gain du retour, payload `ros2 service call`, `build_type` déclaré | extrait du corps du `SKILL.md` le 2026-11-12 pour respecter le budget de 12 000 octets |

Ces trois fichiers ne viennent pas de l'amont : une mise à jour par recopie (voir §5) les écrase si
l'on ne les réapplique pas, et `scripts/__init__.py` (vide, propre à cette installation) doit être
recréé pour que `pytest` importe `scripts` du dépôt et non le paquet résiduel de `~/.local`.

## 4. Outils (15 scripts)

| Script | Rôle | Exécution réelle sur ce robot |
|---|---|---|
| `qos_audit.py` | Audit statique des déclarations QoS d'un paquet | `yahboomcar_bringup` : 0 incompatibilité confirmée, 1 point non résolu, code 0 |
| `qos_checker.py` | Comparaison d'un profil éditeur / abonné, 7 préréglages | `--help` vérifié |
| `launch_validator.py` | Analyse statique de fichiers `*.launch.py` | `slam_launch.py` : aucun problème ; `bridge_launch.py` : 2 avertissements |
| `launch_supervisor.py` | Exécution d'un launch autorisé avec gestion de SIGINT | `--help` vérifié, non exécuté (démarre des processus réels) |
| `rosbag2_qos_checker.py` | Compatibilité QoS d'une relecture de bag | `--help` vérifié, aucun bag présent sur le disque |
| `create_package.py` | Génération de paquets (`cpp`, `python`, `interfaces`, `hardware_interface`) | `--help` vérifié |
| `validate_skill.py` | Contrôles de packaging du skill | `status: pass`, 0 erreur, corps de 195 lignes / 11 609 octets, 41 fichiers référencés |
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
| Chargement du corps | `skill_view("ros2-engineering-skills")` : 179 lignes, 31 références, 16 fichiers de `scripts/` |
| Validation de packaging | `validate_skill.py` : `status: pass`, 0 erreur, 0 avertissement, corps de 11 609 octets |
| Suite de tests du dépôt | 2 188 réussis, 0 échec, 0 ignoré (2026-11-12, 152 s) |
| Budget du corps | 11 609 / 12 000 octets — le corps de 1.7.2 en faisait 20 441 et échouait sur `tests/test_selected_body.py` |
| Bibliothèque YAML | PyYAML 6.0.2 présente pour Python 3.10 |

Commande de la suite, telle qu'exécutée :

```
unset VIRTUAL_ENV PYTHONPATH
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
source /opt/ros/humble/setup.bash
cd ~/.hermes/skills/robotics/ros2-engineering-skills
PYTHONPATH="$PWD:$PYTHONPATH" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /usr/bin/python3 -m pytest -q
→ 2188 passed in 152.37s
```

Trois conditions, chacune vérifiée par l'échec obtenu sans elle :

1. **PATH nettoyé du venv Hermes** : sinon CMake prend le `python3` du venv pour
   `ament_cmake_core/templates_2_cmake.py`, qui ne connaît pas `ament_package`, et
   `test_probe_wiring_records_the_cache_contract[fails]` échoue — c'était le seul échec de la
   version 1.7.2, d'origine environnementale.
2. **ROS Humble sourcé** : sans lui, `PYTHONPATH` ne contient pas
   `/opt/ros/humble/lib/python3.10/site-packages` et le même test échoue sur `ament_package`.
3. **`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`** : le plugin `launch_testing` de Humble déclare
   `pytest_pycollect_makemodule(path, parent)`, signature refusée par pytest 9.2.0 et qui empêche
   toute collecte.

Contournement propre à ce poste : un paquet Python `scripts` résiduel dans
`~/.local/lib/python3.10/site-packages/` (sans `dist-info`) masque le dossier du dépôt ; les tests
importent `from scripts import ...` et résolvent ce paquet. Un `scripts/__init__.py` vide dans la
copie installée, plus `PYTHONPATH=$PWD`, rétablissent le bon module. Le fichier n'existe pas en
amont : il est propre à cette installation.

## 6. Hooks Claude non applicables

Le dépôt fournit `hooks/hooks.json` (PreToolUse sur `Edit|Write|Bash`, et Stop) exécutant
`scripts/claude_hook.py` avec `${CLAUDE_PLUGIN_ROOT}`. Ces hooks sont propres à Claude Code :
aucune unité Hermes ne les charge et le skill ne déclare pas de hook Hermes. Sous Hermes, la
validation reste manuelle, par appel explicite des scripts listés en §4.

La version 1.8.0 durcit ces hooks, sans effet ici : le contrôle PreToolUse n'émet un avis ROS que si
le contexte ROS du fichier est confirmé (import ROS, manifeste `ament_*` valide dans le dossier ou
au-dessus, import dans les 64 premiers Kio) ; un nouvel analyseur signale, en avertissements
seulement, les commandes `ros2` capables de bouger le matériel ou de modifier une porte de
mouvement (`ros2 topic pub` sur un topic de vitesse, de trajectoire ou de contrôleur, buts de
navigation et de manipulation, changements d'état `ros2 control`, services d'arrêt et
d'habilitation, paramètres de butée et de délai, nœuds de téléopération), avec `category:
actuation` ; les commandes sont lues par un analyseur conscient des guillemets, donc un `grep
"ros2 topic pub /cmd_vel"` est une donnée et `bash -lc '…'` une commande. Ces règles ne remplacent
aucune des règles de la base OKF : la porte d'arrêt de [[directeur_s1]] et les préconditions de
[[navigation_nav2_waypoints]] restent les seules autorisations de mouvement.

## 7. Limites

| Limite | Conséquence |
|---|---|
| Validateurs statiques | `qos_audit.py` ne voit ni les remaps, ni les surcharges YAML, ni les défauts RMW ; la confirmation exige `ros2 topic info -v` |
| Aucune exécution matérielle | `launch_supervisor.py` démarre des processus réels ; son usage relève de l'autorisation d'exploitation |
| Évaluations du dépôt | Les captures d'évaluation sont des fixtures, pas une mesure de qualité sur ce robot |
| Connaissance multi-distribution | Le skill décrit Humble, Iron, Jazzy, Kilted ; la version en service ici est Humble, seule à faire foi |
| Pas de provenance Git dans la copie | Aucun `.git` dans `~/.hermes/skills/...` : `hermes plugins check-updates` ne s'applique pas, la mise à jour est une recopie (§5) suivie de la réapplication des fichiers de §3.1 |
| Leçons de terrain hors du corps | `field-lessons.md` n'est chargé que si l'agent suit la ligne du routeur ; le corps ne porte plus que le renvoi, contrainte du budget de 12 000 octets |

## 8. Voir aussi

- Inventaire des skills de l'agent : `docs/skills/index.md` du dépôt, publié sur le site (menu **Skills**)
- Graphe ROS 2 et nœuds : [[ros2_graph_clawbot]]
- Pont LLM audité : [[llm2ros_bridge]], [[llm2ros_bridge_architecture]]
- Conventions de documentation : [[index]]
