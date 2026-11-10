---
title: "Spécification — test de santé des périphériques du robot (HLT)"
date: "2026-11-10T08:12:00+08:00"
author: "Hermes Agent"
tags: [software, specification, health-check, peripheriques, ros2, diagnostic, tests]
status: actif
---

# Spécification — test de santé des périphériques (HLT)

> Décisions D-20, D-22 et D-23 tranchées le 2026-11-10 ; D-21 reste non tranchée et ses seuils sont
> appliqués en valeur provisoire, signalée dans chaque rapport.

## 1. Objet et périmètre

Ce document spécifie un **test de santé en lecture seule** qui vérifie que le robot voit bien les
périphériques qui comptent : caméra, profondeur, IMU, carte de commande des roues, batterie, lidar,
manette. Il répond à une question unique : *les capteurs et actionneurs déclarés sont-ils présents,
identifiés, et produisent-ils des données à la cadence attendue ?*

Ce que le test de santé **n'est pas** :

| Ce n'est pas | Pourquoi |
|---|---|
| un déclencheur | les déclencheurs (`TRG-01` à `TRG-14`, [[llm2ros_mcp_specification]] §3) produisent des incidents et ouvrent un cycle S2 ; le test de santé produit des mesures et un verdict |
| une action de réparation | aucune écriture, aucun redémarrage de service, aucun `param_set` ; la réparation relève de l'intervention humaine ou de S2 |
| un diagnostic de cause | il établit *qu'*une voie est rompue, pas *pourquoi* ; la cause se cherche ensuite dans les journaux |

Le test de santé est la **source de mesure** des déclencheurs `TRG-01` (nœud absent), `TRG-03` (topic
muet) et `TRG-04` (cadence basse) : les sondes produisent des mesures datées, le moteur de
déclenchement décide. Aucune règle n'est dupliquée entre les deux (exigence HLT-14).

## 2. État mesuré du robot au 2026-11-10T08:06:06+08:00

Mesures relevées avant d'écrire cette spécification, domaine ROS 2 = 28.

| Périphérique | Identité constatée | Nœud | Cadence mesurée | Verdict attendu |
|---|---|---|---|---|
| Caméra couleur | `/dev/video0`, `0c45:6340 Sonix USB_2.0_Camera` | `/camera/camera` | `/camera/color/image_raw` 20,077 Hz (nominal 20) | ok |
| Caméra profondeur | fonction USB `2bc5:060f ORBBEC Depth Sensor` | `/camera/camera` | `/camera/depth/image_raw` 30,007 Hz (nominal 30) | ok |
| IMU | intégrée à la carte de commande | `/driver_node` | `/imu/data_raw` 9,999 Hz (nominal 10) | ok |
| Carte de commande | `/dev/myserial` → `ttyUSB1`, `1a86:7523 CH340`, tenue ouverte par le PID 5976 | `/driver_node` | — (liaison série ouverte) | ok |
| Batterie | tension seule (aucune jauge) | `/driver_node` | `/voltage` 9,999 Hz, **11,899 999 V** | ok |
| Lidar | YDLIDAR TG30, CP2102 `10c4:ea60` | `ydlidar_ros2_driver` | `/scan` 10,154 Hz | ok |
| Manette | **aucun `/dev/input/js*`** | `clawbot-joy-teleop.service` actif | — | failed |
| Disque racine | `/dev/nvme0n1p1` | — | 12 Go libres sur 147 Go (92 %) | degraded (D-07) |
| Températures | `cpu` 54, `gpu` 50, `cv0` 49, `cv1` 48, `cv2` 45, `soc0` 48 °C | — | — | ok |

Trois constats qui commandent la conception :

1. **L'identité matérielle ne se déduit ni du nom ni de l'index.** Les deux nœuds V4L (`/dev/video0`,
   `/dev/video1`) appartiennent au même couple `0c45:6340`, alors que `lsusb` expose par ailleurs
   `2bc5:050f` et `2bc5:060f` pour les fonctions Orbbec. Deux adaptateurs série coexistent
   (`1a86:7523` = carte de commande, `Silicon_Labs_CP2102` = autre). Un test qui vérifie « un
   `/dev/video*` existe » ou « un `ttyUSB*` existe » valide le mauvais périphérique sans le dire.
2. **Un service actif ne prouve pas qu'un périphérique est là.** `clawbot-joy-teleop.service` est
   `active (running)` alors qu'aucun périphérique d'entrée manette n'existe. Vérifier l'unité systemd
   est un indice, jamais une preuve.
3. **Le lidar était présent alors que `/scan` manquait** ([[ERR-2026-11-10-001_absence_topic_scan]]).
   Le capteur est un YDLIDAR TG30 sain : seule l'unité qui lance le pilote manquait. Un topic absent ne
   prouve pas un matériel absent — le test de santé sonde désormais l'adaptateur **et** le topic.

## 3. Inventaire déclaré

L'inventaire est **unique et versionné** : c'est lui qui décide ce qu'on vérifie. Un périphérique
absent de l'inventaire n'est pas testé, et son absence n'est pas un défaut.

| ID | Périphérique | Requis | Sonde physique | Sonde ROS | Sonde fonctionnelle |
|---|---|---|---|---|---|
| PER-01 | Caméra couleur | oui | couple `0c45:6340` + nœud V4L résolu par udev | `/camera/color/image_raw` | 640×480, `rgb8`/`yuyv`, `frame_id` non vide |
| PER-02 | Caméra profondeur | oui | fonction USB `2bc5:060f` | `/camera/depth/image_raw` | 640×480, 16 bits, `frame_id` non vide |
| PER-03 | IMU | oui | carte de commande présente | `/imu/data_raw` | quaternion normalisé (norme 1 ± 0,05) |
| PER-04 | Carte de commande | oui | `/dev/myserial` résolu vers le bon `by-id`, `1a86:7523` | `/driver_node` dans le graphe | port ouvert par un seul processus |
| PER-05 | Batterie | oui | — | `/voltage` | tension dans une plage physique 8–13 V |
| PER-06 | Lidar YDLIDAR TG30 | oui | CP2102 `10c4:ea60`, `/dev/ydlidar` | `/scan` | 10 Hz, `frame_id: laser` |
| PER-07 | Manette | non | `/dev/input/js*` avec couple propriétaire | — | au moins un bouton lu |
| PER-08 | Chaîne de détection YOLO | non | — | point d'entrée `http://127.0.0.1:8003/health` | `200` — le service publie en HTTP, aucun éditeur sur `/camera/detection_image` |
| PER-09 | Arbre TF | oui | — | `/tf` | `base_link`, `odom`, `map` présents (aujourd'hui absents : [[ERR-2026-11-10-003_arbre_tf_incomplet]]) |

## 4. Modèle de sonde

Chaque sonde applique le même contrat, quel que soit le niveau :

| Champ | Sens |
|---|---|
| `probe` | identifiant stable de la sonde (`PER-01/device`, `PER-01/rate`…) |
| `level` | `device` (noyau, USB, udev), `ros` (graphe, topic), `functional` (contenu du message) |
| `status` | `ok`, `degraded`, `failed`, `unavailable`, `skipped` |
| `observed` | mesure brute, avec unité |
| `threshold` | seuil appliqué, tel qu'écrit ici |
| `measured_at` | horodatage ISO 8601 |
| `error_code` | code stable (`HLT-E-*`), `null` si `ok` |
| `detail` | une phrase factuelle, sans interprétation |

Une sonde ne retourne jamais un booléen nu : une mesure sans seuil n'est pas vérifiable, et un
`false` sans code ne se diagnostique pas (exigence HLT-04).

## 5. Verdicts et agrégation

| Verdict | Règle |
|---|---|
| `ok` | toutes les sondes applicables sont `ok` |
| `degraded` | au moins une sonde `degraded`, aucune `failed` |
| `failed` | au moins une sonde `failed` sur un périphérique `requis: true` |
| `unavailable` | aucune sonde applicable : périphérique déclaré non installé (PER-06) |
| `skipped` | périphérique désactivé par configuration, ou sonde non applicable au niveau demandé |

Verdict global = le plus grave de l'inventaire, dans l'ordre `failed` > `degraded` > `unavailable` >
`ok`. Un `failed` sur un périphérique `requis: false` ne dégrade pas le verdict global, mais reste
visible dans le rapport et dans le journal (exigence HLT-09).

## 6. Seuils

| Sonde | `ok` | `degraded` | `failed` |
|---|---|---|---|
| âge du dernier message | ≤ 3 × période déclarée | > 3 et ≤ 10 périodes | > 10 périodes, ou aucun message |
| cadence (fenêtre 5 s) | ≥ 80 % du nominal | ≥ 50 % et < 80 % | < 50 % |
| nœud dans le graphe | présent en < 3 s | présent, mais aucun topic publié | absent après 3 s |
| port série | ouvert par un seul processus attendu | ouvert par plusieurs processus | absent, permission refusée, ou non résolu |
| température | ≤ 70 °C | > 70 et ≤ 80 °C | > 80 °C |
| tension | ≥ 11,0 V | ≥ 10,5 et < 11,0 V | < 10,5 V |
| disque libre | ≥ 5 Go | ≥ 1 et < 5 Go | < 1 Go |

Les seuils de tension et de disque proviennent de D-06 et D-07, **non validés** : ils sont marqués
`provisional: true` dans la sortie, comme dans [[llm2ros_mcp_specification]] §10.

## 7. Sortie

```json
{
  "health_version": "1.0",
  "checked_at": "2026-11-10T08:06:06+08:00",
  "duration_ms": 4210,
  "verdict": "degraded",
  "ros": {"domain_id": 28, "node_count": 7},
  "peripherals": [
    {
      "id": "PER-01",
      "name": "camera couleur",
      "required": true,
      "verdict": "ok",
      "identity": {"usb": "0c45:6340", "device": "/dev/video0"},
      "probes": [
        {"probe": "PER-01/device", "level": "device", "status": "ok",
         "observed": {"present": true}, "threshold": {"present": true},
         "measured_at": "2026-11-10T08:06:06+08:00", "error_code": null, "detail": ""},
        {"probe": "PER-01/rate", "level": "ros", "status": "ok",
         "observed": {"rate_hz": 20.077, "age_s": 0.01}, "threshold": {"min_rate_hz": 16.0},
         "measured_at": "2026-11-10T08:06:10+08:00", "error_code": null, "detail": ""}
      ]
    }
  ],
  "unavailable": ["PER-06 lidar: HLT-E-NOT-INSTALLED"],
  "provisional": ["voltage: D-06", "disk_free: D-07"]
}
```

Contraintes : `health_version` permet de versionner le schéma (HLT-07) ; la taille reste ≤ 64 Ko ;
aucun chemin de credentials, aucun jeton (HLT-17) ; l'ordre des périphériques suit l'inventaire, pas
l'ordre de découverte, pour que deux rapports se comparent ligne à ligne.

## 8. Codes d'erreur

| Code | Sens |
|---|---|
| `HLT-E-DEVICE-ABSENT` | aucun nœud de périphérique ne correspond à l'identité déclarée |
| `HLT-E-IDENTITY-MISMATCH` | un nœud existe à l'emplacement attendu, mais l'identité USB ne correspond pas |
| `HLT-E-PERM` | nœud présent, droits insuffisants pour l'ouvrir en lecture |
| `HLT-E-USED-BY-OTHER` | périphérique tenu par un processus non déclaré |
| `HLT-E-NODE-ABSENT` | nœud ROS déclaré absent du graphe après le délai |
| `HLT-E-TOPIC-SILENT` | aucun message reçu dans la fenêtre |
| `HLT-E-RATE-LOW` | cadence mesurée sous le seuil |
| `HLT-E-FRAME-INVALID` | message reçu, contenu incohérent (dimensions, encodage, quaternion) |
| `HLT-E-NOT-INSTALLED` | périphérique déclaré non installé sur ce robot |
| `HLT-E-UNAVAILABLE` | mesure impossible pour une raison déclarée (permission, bus absent) |
| `HLT-E-TIMEOUT` | sonde interrompue avant son délai |

## 9. Points d'entrée

| Usage | Forme | Exigence |
|---|---|---|
| opérateur | `python3 -m bridge_mcp.health --json` ; codes de sortie 0 `ok`, 1 `degraded`, 2 `failed`, 3 erreur interne ; `--service-mode` sort 0 sauf erreur interne, pour ne pas marquer l'unité systemd en échec | HLT-12 |
| S2 | outil MCP `diagnostics` (déjà au catalogue) et ressource `health://etat` | HLT-13 |
| surveillance | `clawbot-health.service` (oneshot) au démarrage, et `run_and_notify(reason=…)` appelé par S1 à chaque anomalie ; pas de timer périodique | HLT-15 |
| déclencheurs | les sondes remplissent `Observation` (`bridge_mcp/observations.py`), consommée par `TriggerEngine` | HLT-14 |

Le timer n'agit jamais : il observe et journalise. Toute correction reste une décision — humaine, ou
de S2 via les outils d'intervention encadrés par l'arbitre.

## 10. Exigences

| ID | Exigence | Critère d'acceptation |
|---|---|---|
| HLT-01 | L'inventaire des périphériques est déclaratif, versionné et unique ; il porte l'identité attendue, le caractère requis et les sondes applicables | Modifier l'inventaire suffit à changer ce qui est testé, sans toucher au code des sondes |
| HLT-02 | Chaque périphérique est identifié par son identité matérielle (couple VID:PID, chemin `by-id`, série si disponible), jamais par un index `/dev/videoN` ni `/dev/ttyUSBN` | Un périphérique déplacé vers un autre index est retrouvé ; un périphérique étranger au même index est déclaré `HLT-E-IDENTITY-MISMATCH` |
| HLT-03 | Trois niveaux de sonde indépendants : `device`, `ros`, `functional` ; un niveau en échec n'empêche pas les autres de rendre leur verdict | Couper le service caméra laisse la sonde `device` `ok` et la sonde `ros` `failed` |
| HLT-04 | Aucune sonde ne retourne un booléen nu : toute mesure porte `observed`, `threshold`, `measured_at`, et un `error_code` en cas d'échec | Validation de schéma sur 100 rapports générés |
| HLT-05 | Toute sonde a un délai borné ; le rapport complet est produit en moins de 10 s, aucune sonde ne dépasse 2 s | Mesure de `duration_ms` sur 100 exécutions |
| HLT-06 | Le test n'écrit rien : aucun fichier hors `--report <chemin>`, aucune publication, aucun `param_set`, aucun redémarrage d'unité | Contrôle du code (aucun `open(..., "w")`, `publish`, `subprocess` d'écriture) et empreinte des unités avant/après |
| HLT-07 | Le rapport est un JSON stable et versionné (`health_version`) ; deux exécutions sans changement donnent les mêmes verdicts, hors horodatages | Comparaison de deux rapports successifs |
| HLT-08 | Un périphérique déclaré non installé (lidar) est `unavailable` avec `HLT-E-NOT-INSTALLED`, jamais `failed` ni ignoré | Retrait du lidar de l'inventaire → aucun verdict, ajout → `unavailable` |
| HLT-09 | Un `failed` sur un périphérique `requis: false` n'abaisse pas le verdict global, mais figure dans le rapport et le journal | Manette absente → verdict global inchangé, entrée `PER-07` en `failed` |
| HLT-10 | Un service systemd actif ne vaut pas preuve de présence : le verdict repose sur le périphérique et les données, jamais sur `ActiveState` | Manette absente alors que `clawbot-joy-teleop.service` est actif → `failed` |
| HLT-11 | La sonde `ros` initialise un contexte `rclpy` en lecture seule dans le domaine courant, ne crée aucun éditeur, et le détruit proprement | Aucun éditeur visible dans `ros2 node info` du nœud de sonde ; sortie sans exception |
| HLT-12 | Interface ligne de commande avec sortie JSON et codes de sortie 0/1/2/3 | `python3 -m bridge_mcp.health --json` retourne le bon code selon le verdict |
| HLT-13 | Le rapport alimente l'outil MCP `diagnostics` et la ressource `health://etat` sans duplication de logique | `diagnostics` retourne exactement le rapport de la dernière exécution, horodaté |
| HLT-14 | Le test de santé ne redéfinit aucune règle de déclenchement : il alimente `Observation`, `TriggerEngine` décide | Les seuils de cadence et d'âge sont lus depuis `bridge_mcp/triggers.py`, pas réécrits |
| HLT-15 | Exécution au démarrage par unité oneshot, et à chaque anomalie émise par S1 ; aucune exécution périodique, aucune action corrective | `systemctl start clawbot-health.service` produit un rapport et laisse l'unité en succès ; le journal contient une ligne `notification: <statut>` |
| HLT-16 | Chaque verdict cite l'exigence et l'inventaire qui le justifient (`spec_refs`) | Revue de la matrice exigence → test |
| HLT-17 | Aucun secret, aucun jeton, aucun chemin de credentials dans le rapport | Analyse statique sur 100 rapports |
| HLT-18 | Aucune donnée inventée : une mesure impossible est `null` avec code, jamais `0` ni `false` implicite | Rapport sur périphérique débranché : mesures `null` et codes explicites |

## 11. Tests prévus, à écrire avant le code

| Exigence | Test |
|---|---|
| HLT-02 | faux arbre `/dev` et `/sys` : index déplacé, périphérique étranger au même index |
| HLT-03 | service caméra arrêté (simulation) : `device` `ok`, `ros` `failed` |
| HLT-04, HLT-07 | validation de schéma sur 100 rapports ; comparaison de deux rapports |
| HLT-05 | 100 exécutions contre un faux graphe : `duration_ms` borné |
| HLT-06 | aucune écriture : inspection des appels et empreinte des unités |
| HLT-08, HLT-09 | lidar retiré / ajouté ; manette absente avec service actif |
| HLT-10 | unité systemd factice active, périphérique absent → `failed` |
| HLT-11 | contexte `rclpy` détruit, aucun éditeur |
| HLT-12, HLT-13 | CLI et outil MCP sur le même rapport |
| HLT-18 | périphérique débranché → `null` + code, jamais `0` |

Les tests tournent en domaine 99, sur un faux arbre de périphériques : aucun accès au robot réel, qui
reste en domaine 28 ([[llm2ros_mcp_test_plan]] §3).

## 12. Décisions requises avant l'implémentation

| ID | Question | Proposition |
|---|---|---|
| D-20 | Quels périphériques sont `requis: true` ? | **Tranchée le 2026-11-10 :** le statut des périphériques est envoyé à l'humain par Telegram ; aucune barrière ni action locale. `requis` reste déclaré pour le verdict, mais `ACTIONS_ON_FAILURE` est vide. Requis : caméra couleur, profondeur, IMU, carte de commande, batterie, arbre TF |
| D-21 | Seuils de cadence et d'âge | **Non tranchée.** Valeurs appliquées à titre provisoire : `ok` ≥ 80 % du nominal, `degraded` ≥ 50 %, `failed` < 50 % ; âge `failed` au-delà de 10 périodes. Signalées `provisional` dans chaque rapport |
| D-22 | Période d'exécution | **Tranchée le 2026-11-10 :** au démarrage et à chaque anomalie émise par le graphe de S1, sans exécution périodique |
| D-23 | Que faire d'un `failed` ? | **Tranchée le 2026-11-10 :** message à l'humain par Telegram, aucune relance automatique |

## 13. Implémentation et mesures réelles (2026-11-10)

| Module | Rôle |
|---|---|
| `bridge_mcp/health.py` | inventaire, vues `device` et `ros`, agrégation des verdicts, CLI, `run_and_notify` |
| `bridge_mcp/notify.py` | message humain et envoi Telegram, jetons lus dans `/etc/clawbot/telegram-{token,chat}` |
| `services/clawbot-health.service` | oneshot au démarrage, `--notify --reason demarrage --service-mode` |
| `tests/mcp_bridge/health/` | 33 tests : inventaire, sondes, rapport, notification, endpoint HTTP |

Rapport réel, domaine 28, deux exécutions consécutives identiques :

```
verdict: failed | durée: 7216 ms
  PER-01 camera couleur         ok          cadence 20,087 Hz
  PER-02 camera profondeur      ok          cadence 30,166 Hz
  PER-03 centrale inertielle    ok          cadence 10,397 Hz
  PER-04 carte de commande      ok          port tenu par un seul processus
  PER-05 batterie               ok          cadence 10,399 Hz
  PER-06 lidar                  unavailable non installé
  PER-07 manette                failed      aucun noeud d'entree
  PER-08 chaine de detection    ok          HTTP 200
  PER-09 arbre TF               failed      base_link, odom, map absents
notification: not_configured (livre=False)
```

Quatre défauts trouvés **par la mesure réelle**, invisibles sur les faux systèmes :

| Défaut | Effet constaté | Correction |
|---|---|---|
| Âge pris sur `header.stamp` | `/voltage` (`std_msgs/Float32`, sans en-tête) jugé muet alors qu'il publiait à 10 Hz | âge d'arrivée horodaté à la réception quand l'en-tête manque |
| Comparaison de noms de nœuds avec barre oblique | `/driver_node` déclaré absent alors qu'il tournait | comparaison normalisée |
| Découverte DDS comptée dans la fenêtre | caméra 20 Hz mesurée à 15–18 Hz, verdict `degraded` erratique | fenêtre de découverte de 1,5 s puis compteurs remis à zéro |
| Cadence calculée sur la durée de fenêtre | 18,4 Hz au lieu de 20,08 Hz, verdict instable d'une exécution à l'autre | cadence calculée sur l'intervalle entre premier et dernier message |
| `PER-08` déclaré sur un topic | `/camera/detection_image` : 0 éditeur, service YOLO actif mais en HTTP | sonde HTTP sur `:8003/health` |

Le service systemd sort en succès même quand le verdict est `failed` (`--service-mode`) : le verdict est
dans le rapport et dans le message, pas dans le code de sortie de l'unité.

## 14. Voir aussi

- [[llm2ros_mcp_specification]] — déclencheurs et contexte d'incident
- [[llm2ros_mcp_test_plan]] — architecture de la suite, isolation
- [[orbbec_astra_pro_plus]] — caméra Astra Pro+
- [[rosmaster_x3_mcu]] — carte de commande et liaison série
- [[batterie_principale]] — tension seule, pas de jauge
- [[ros2_graph_clawbot]] — graphe constaté
- [[systemd_robot_services]] — unités en service
- [[ERR-2026-11-10-001_absence_topic_scan]], [[ERR-2026-11-10-003_arbre_tf_incomplet]]
