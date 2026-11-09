---
title: "ERR-2026-11-10-004 — exécution de commande non authentifiée sur le pont LLM"
date: "2026-11-10T06:21:30+08:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, securite, injection, http, llm]
status: ouvert
---

# ERR-2026-11-10-004 — exécution de commande non authentifiée sur le pont LLM

| Champ | Valeur |
|---|---|
| Identifiant | `ERR-2026-11-10-004` |
| Horodatage de détection | 2026-11-10T06:21:30+08:00 (CST) |
| Composant concerné | [[llm2ros_bridge]] — `api_server` port 8000 |
| Interface concernée | HTTP `/command` (outil `Speak`), HTTP `/evolution/build` |
| Domaine ROS 2 | 28 |
| Gravité d'exploitation | Critique : exécution de code arbitraire sous l'utilisateur `jetson`, sans authentification, depuis le réseau local |
| Statut | ouvert |
| Mitigation appliquée | Aucune modification de la pile en exécution ; preuve d'exécution supprimée après constat |

## 1. Nature de l'échec

Le pont expose sur toutes les interfaces réseau, sans authentification, deux chemins qui transmettent une donnée contrôlée par l'appelant à un interpréteur de commandes :

1. L'outil `Speak` concatène le texte fourni dans une commande passée à `std::system` :

```cpp
// src/bridge_node.cpp:106
std::string cmd = "espeak-ng \"" + text + "\" 2>/dev/null";
int rc = std::system(cmd.c_str());
```

2. La route `/evolution/build` concatène le nom de paquet fourni dans une commande `colcon` exécutée de la même manière :

```cpp
// src/api_server.cpp:381-388
std::string pkg = req.value("package", "ros2_llm_bridge_cpp");
std::string cmd = "cd /home/jetson/clawbot && source /opt/ros/humble/setup.bash && "
                  "colcon build --packages-select " + pkg +
                  " --cmake-args -DCMAKE_BUILD_TYPE=Release 2>&1";
int rc = std::system(cmd.c_str());
```

Aucune authentification n'est active : le service ne définit pas `API_KEY`, condition d'activation du contrôle de jeton (`src/api_server.cpp:334-347`).

## 2. Preuves

### 2.1 Surface exposée

```
$ ss -ltnp | grep -E ":8000|:8001"
LISTEN 0 16 0.0.0.0:8000 0.0.0.0:* users:(("api_server",pid=1403,fd=23))
LISTEN 0 2048 0.0.0.0:8001 0.0.0.0:* users:(("python3",pid=1388,fd=36))

$ grep -l "API_KEY" /etc/systemd/system/ros2-*.service
(aucune sortie — aucune unité ne définit API_KEY)

$ curl -s -o /dev/null -w "%{http_code}\n" http://192.168.1.47:8000/health
200
```

### 2.2 Preuve d'exécution de commande

Requête émise le 2026-11-10 à 06:21:30 CST, sans jeton :

```
$ curl -s -X POST http://localhost:8000/command -H 'Content-Type: application/json' \
    -d '{"function":"Speak","arguments":{"text":"test\" ; touch /tmp/llm_bridge_injection_proof ; echo \""}}'
{"result":"Speak: \"test\" ; touch /tmp/llm_bridge_injection_proof ; echo \"\" (TTS via espeak-ng)"}

$ ls -l /tmp/llm_bridge_injection_proof
-rw-r--r-- 1 jetson jetson 0 Nov 10 06:21 /tmp/llm_bridge_injection_proof
```

Le fichier a été créé par la commande injectée : la chaîne fournie à l'outil `Speak` est interprétée par le shell. Le fichier de preuve a été supprimé après constat.

### 2.3 Portée de l'exécution

| Élément | Valeur | Source |
|---|---|---|
| Utilisateur du processus | `jetson` (uid 1000) | `ss -ltnp` |
| Groupes de l'utilisateur | `sudo`, `docker`, `i2c`, `gpio`, `video`, `gpio` | `id` |
| Élévation de privilèges | Possible via l'appartenance au groupe `docker` et l'accès `sudo` sans mot de passe | `sudo -n true` → code 0 |
| Accès réseau requis | Aucun : écoute sur `0.0.0.0`, atteignable depuis le Wi-Fi | `curl http://192.168.1.47:8000/health` → 200 |
| Authentification requise | Aucune | `API_KEY` absent |

Conséquence : tout hôte du réseau local peut piloter le robot et exécuter des commandes en tant que `jetson`, avec élévation de privilèges possible vers `root` par le groupe `docker`.

## 3. Actions de mitigation

| Horodatage | Action | Résultat mesuré |
|---|---|---|
| 2026-11-10T06:21:30+08:00 | Constat par preuve d'exécution, suppression du fichier témoin | Pile inchangée, 8 unités toujours actives |
| 2026-11-10T06:34:00+08:00 | Consignation des exigences de correction (EF-27, EF-28, EF-37, ENF-07, ENF-08) | [[llm2ros_bridge_specification]] |

Aucune mesure de confinement n'a été appliquée : une modification en exploitation exige une fenêtre de maintenance et l'accord de l'exploitant. Le plan E0 de [[llm2ros_bridge_coherence_et_approche]] §10 décrit les quatre changements à appliquer : écoute sur `127.0.0.1`, `API_KEY` obligatoire, retrait des routes `/evolution/*`, remplacement de `std::system` par une exécution sans shell.

## 4. Conditions de clôture

La trace passe à `validé` lorsque les quatre mesures suivantes réussissent :

1. `ss -ltnp | grep :8000` montre `127.0.0.1:8000` et non `0.0.0.0:8000`.
2. `curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/command -H 'Content-Type: application/json' -d '{"function":"Stop"}'` retourne `401` sans jeton.
3. La même requête avec le texte `test" ; touch /tmp/x ; echo "` ne crée aucun fichier `/tmp/x` (vérifié par test automatisé).
4. `POST /evolution/build` retourne `404` ou `403` sur le service de production.

## 5. Voir aussi

- État constaté du composant : [[llm2ros_bridge]]
- Architecture et chemins d'exécution : [[llm2ros_bridge_architecture]]
- Exigences violées : [[llm2ros_bridge_specification]]
- Analyse de cohérence et plan de correction : [[llm2ros_bridge_coherence_et_approche]]
- Autres traces ouvertes : [[ERR-2026-11-10-001_absence_topic_scan]], [[ERR-2026-11-10-002_espace_disque_critique]], [[ERR-2026-11-10-003_arbre_tf_incomplet]]
