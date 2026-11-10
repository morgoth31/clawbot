---
title: "ERR-2026-11-10-005 — pytest interrompu par les plugins launch_testing de ROS 2 Humble"
date: "2026-11-10T08:44:00+08:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, ros2, pytest, launch_testing, tests]
status: ouvert
---

# ERR-2026-11-10-005 — pytest interrompu par les plugins launch_testing de ROS 2 Humble

| Champ | Valeur |
|---|---|
| Identifiant | `ERR-2026-11-10-005` |
| Horodatage de détection | 2026-11-10T08:38:12+08:00 (CST) |
| Composant concerné | toute exécution `pytest` dans un shell où `/opt/ros/humble/setup.bash` est chargé |
| Versions | `pytest` 9.2.0 ; `launch_testing` 1.0.14 ; `launch_testing_ros` 0.19.13 ; ROS 2 Humble |
| Gravité d'exploitation | Blocage : aucune collecte de tests, aucun rapport |
| Statut | ouvert — contournement en place, cause non corrigée à la source |
| Mitigation appliquée | `-p no:launch_testing -p no:launch_ros` dans `tests/mcp_bridge/pytest.ini` |

## 1. Nature de l'échec

Dans un shell où l'environnement ROS 2 Humble est chargé, `python3 -m pytest` s'arrête avant toute
collecte :

```
Error while loading plugin "pytest11".
pluggy._manager.PluginValidationError: Plugin 'launch_testing' for hook 'pytest_pycollect_makemodule'
hookimpl definition: pytest_pycollect_makemodule(path, parent)
Argument(s) {'path'} are declared in the hookimpl but can not be found in the hookspec
```

Une fois ce premier plugin neutralisé, un second défaut apparaît, du même ordre :

```
pluggy._manager.PluginValidationError: unknown hook 'pytest_launch_collect_makemodule'
in plugin <module 'launch_testing_ros_pytest_entrypoint'>
```

Aucune assertion n'est évaluée : le code testé ne peut être ni validé ni invalidé.

## 2. Cause

`launch_testing` et `launch_ros` sont enregistrés comme plugins `pytest11` par leurs points d'entrée
(`/opt/ros/humble/lib/python3.10/site-packages/*.egg-info/entry_points.txt`). Ils déclarent des hooks
supprimés ou modifiés depuis pytest 8 : `pytest_pycollect_makemodule(path, parent)` n'accepte plus
l'argument `path`, et `pytest_launch_collect_makemodule` n'existe plus dans la spécification.

L'incompatibilité vient de l'écart entre la distribution ROS 2 Humble (2022, pytest 6/7) et le pytest
installé (9.2.0). Elle n'est pas propre au pont : toute suite pytest exécutée dans un shell ROS chargé
sur ce poste est concernée, y compris via `colcon test`.

## 3. Preuves

```
$ /usr/bin/python3 -m pytest --version
pytest 9.2.0

$ cat /opt/ros/humble/lib/python3.10/site-packages/launch_testing-1.0.14.egg-info/entry_points.txt
[pytest11]
launch_testing = launch_testing.pytest.hooks

$ cat /opt/ros/humble/lib/python3.10/site-packages/launch_testing_ros-0.19.13.egg-info/entry_points.txt
[pytest11]
launch_ros = launch_testing_ros_pytest_entrypoint

$ bash -lc 'source /opt/ros/humble/setup.bash && cd ~/clawbot/tests/mcp_bridge && pytest -q'
pluggy._manager.PluginValidationError: Plugin 'launch_testing' for hook 'pytest_pycollect_makemodule'
```

## 4. Mitigation

Les deux plugins sont exclus explicitement dans `tests/mcp_bridge/pytest.ini` :

```
addopts = -q --strict-markers --timeout=60 -p no:launch_testing -p no:launch_ros
```

Vérification après correctif, dans un shell où l'environnement ROS est chargé :

```
$ bash -lc 'source /opt/ros/humble/setup.bash && cd ~/clawbot/tests/mcp_bridge && ROS_DOMAIN_ID=99 pytest'
70 passed in 11.41s

$ ROS_DOMAIN_ID=28 pytest
Exit: ROS_DOMAIN_ID=28 interdit pendant les tests : pollution du graphe réel (ENV-01)
exit=2
```

Le refus du domaine 28 est conservé : il protège le graphe réel et se produit avant toute
initialisation de contexte ROS 2.

## 5. Contournement pour les autres projets

Pour une suite qui ne peut pas modifier son `pytest.ini` :

```
PYTEST_ADDOPTS="-p no:launch_testing -p no:launch_ros" python3 -m pytest
```

La correction à la source consiste soit à exécuter les tests dans un environnement dont le `setup.bash`
n'est pas chargé, soit à aligner `launch_testing` sur le pytest installé. Aucune des deux n'a été
appliquée : la pile ROS 2 en exécution n'a pas été modifiée.

## 6. Portée et suites

Les 70 tests du pont s'exécutent désormais dans les deux environnements (shell nu et shell ROS chargé).
La cause racine reste ouverte pour les autres suites du poste.

## 7. Voir aussi

- [[llm2ros_mcp_test_plan]]
- [[ros2_engineering_skills]]
- [[systemd_robot_services]]
