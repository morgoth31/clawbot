---
title: "Cahier des charges — llm2ros bridge (port LLM → ROS 2 du Clawbot X3)"
date: "2026-11-10T06:28:00+08:00"
author: "Hermes Agent"
tags: [software, llm, ros2, specification, exigences, cahier-des-charges, api]
status: actif
---

# Cahier des charges — llm2ros bridge

Document de référence des exigences du pont entre un modèle de langage et les actionneurs du Clawbot X3. Il remplace le `PRD.md` du dépôt, qui décrit une pile Python (`llm_handler.py`, FastAPI sur 8000) dont le fichier `llm_handler.py` n'existe pas et qui ne correspond pas au composant déployé. État constaté : [[llm2ros_bridge]]. Analyse de cohérence et proposition : [[llm2ros_bridge_coherence_et_approche]].

## 1. Objet et périmètre

**Objet.** Définir les exigences fonctionnelles et non fonctionnelles du service qui transforme un appel d'outil émis par un LLM en actions physiques sur le robot, et qui renvoie au LLM un résultat exploitable.

**Périmètre inclus.** Le service et son contrat HTTP, la validation des arguments, la sécurité d'accès, la sérialisation des actions sur les actionneurs, la traçabilité des décisions et l'interface avec le middleware ROS 2 du robot.

**Périmètre exclu.** Le modèle de langage lui-même et son orchestration ; la pile de navigation Nav2 ; le pilote série du châssis ([[yahboomcar_bringup_driver_node]]) ; la chaîne SLAM.

## 2. Acteurs et cas d'usage

| Acteur | Rôle | Interface |
|---|---|---|
| Agent LLM distant | Émet des appels d'outils, consomme les schémas | HTTP `/tools`, `/command` |
| Opérateur humain | Supervise, change de mode, arrête le robot | HTTP `/mode`, `/command` (`Stop`) |
| Service matériel | Exécute les actions bas niveau, publie sur ROS 2 | HTTP interne 8001 |
| Exploitant système | Démarre, surveille, met à jour | systemd, `/health`, journaux |

Cas d'usage nominaux : déplacement borné, arrêt d'urgence, capture d'image et analyse de scène, détection d'objets, manipulation du bras et de la pince, signalisation lumineuse et sonore, lecture de l'état énergétique.

## 3. Définitions

| Terme | Définition |
|---|---|
| Outil | Capacité exposée au LLM sous forme de fonction JSON nommée |
| Appel d'outil | Message `{"function": <nom>, "arguments": <objet>}` |
| Actionneur | Servo, moteur de roue, pince, buzzer, LED |
| `cid` | Identifiant de corrélation d'une décision LLM jusqu'à l'action physique |
| Watchdog | Mécanisme indépendant du client qui annule un mouvement non renouvelé |
| Mode | État d'exploitation restreignant l'ensemble des outils autorisés |

Légende de l'état constaté (colonne « État ») : **S** satisfait · **P** partiel · **N** non satisfait · **A** absent.

## 4. Exigences fonctionnelles

### 4.1 Contrat d'interface LLM

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| EF-01 | Le service publie la totalité de ses capacités sous forme de schémas JSON conformes au sous-ensemble OpenAI (`type`, `function`, `parameters`) et au format Anthropic (`input_schema`) | `GET /tools` et `GET /tools?format=anthropic` renvoient un tableau dont la longueur égale le nombre d'outils implémentés ; chaque schéma valide contre JSON Schema draft 2020-12 | S |
| EF-02 | Les schémas sont générés depuis une source unique, partagée avec la validation serveur et la documentation | Toute modification d'une borne apparaît simultanément dans `/tools`, dans la validation et dans `/openapi.json` ; aucun test de cohérence ne détecte d'écart | N |
| EF-03 | Chaque réponse est un objet JSON structuré `{"ok":bool, "data":object, "error":{"code","message"}}` | `curl … | jq -r '.data.voltage'` retourne `11.9` sans second décodage | N |
| EF-04 | Le champ `arguments` est accepté en objet JSON et en chaîne JSON encodée | Les deux formes produisent la même exécution ; aucune réponse 400 pour ce motif | N |
| EF-05 | Les erreurs sont typées par un code stable (`E_INVALID_ARG`, `E_UNKNOWN_TOOL`, `E_MODE_FORBIDDEN`, `E_HW_UNREACHABLE`, `E_TIMEOUT`, `E_PREREQ_MISSING`) associé au code HTTP | Table de correspondance publiée ; un test par code | N |
| EF-06 | La version sémantique du service est exposée (`/health`, en-tête) et le code source est versionné | `GET /health` retourne `version` ; `git status --porcelain` ne liste aucune source du service | N |
| EF-07 | Une spécification OpenAPI 3.1 est servie et décrit toutes les routes | `GET /openapi.json` retourne 200 et un document valide | N |

### 4.2 Corrélation et traçabilité

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| EF-08 | Chaque requête reçoit un identifiant de corrélation, retourné au client (`X-Request-Id` et champ `request_id`) | Deux appels successifs retournent deux identifiants distincts, non nuls | N |
| EF-09 | L'identifiant de corrélation est présent dans chaque journal d'exécution, avec outil, arguments normalisés, mode, résultat et durée | `journalctl -u llm-bridge` contient une ligne par appel, corrélable de bout en bout | P |
| EF-10 | Les appels d'outils bruts du LLM sont archivés pour audit (horodatage, nom, arguments, réponse) | Fichier d'audit en ajout seul ; rotation et purge documentées | A |

### 4.3 Mouvement

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| EF-11 | Toute commande de vitesse porte une durée bornée, et l'arrêt effectif survient au plus tard 300 ms après l'échéance | Après un `SetVelocity` de 1,0 s, `/vel_raw` vaut 0,000 m/s à t = 1,3 s | P |
| EF-12 | Une seule commande de mouvement est active à la fois : les commandes concurrentes sont sérialisées ou rejetées avec un code explicite | Deux `SetVelocity` simultanés produisent un ordre déterministe ; aucun arrêt prématuré du mouvement en cours | N |
| EF-13 | `Stop` est prioritaire sur toute autre commande et s'exécute même lorsqu'une action est en cours | Un `Stop` émis pendant un `NavigateTo` remet la vitesse à zéro en moins de 100 ms | N |
| EF-14 | Le watchdog d'arrêt est indépendant du client HTTP et du processus serveur | Arrêt du processus du pont pendant un mouvement → vitesse nulle dans `MOTION_WATCHDOG_S` (1,5 s) | S |
| EF-15 | Les bornes de vitesse ont une source unique de vérité, identique dans le schéma, la validation, le service matériel et la documentation | Recherche d'une valeur de borne dans le code : une seule occurrence non générée | N |

### 4.4 Navigation

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| EF-16 | Une commande de navigation n'est acceptée que si ses prérequis sont présents : odométrie, transformation `map→odom→base_link`, carte d'occupation | Sans `/odom` ni TF `base_link`, l'appel retourne `E_PREREQ_MISSING` avec la liste des éléments manquants | N |
| EF-17 | La navigation s'appuie sur un contrôleur en boucle fermée (Nav2) ; aucun déplacement en boucle ouverte n'est exposé sous le nom de navigation | L'outil cible une action Nav2 ; la progression est mesurée sur `/odom` | N |
| EF-18 | Le référentiel des coordonnées cibles est déclaré et vérifié à l'exécution | Le schéma nomme le référentiel (`map`) ; un appel avec un référentiel absent échoue explicitement | N |

### 4.5 Perception

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| EF-19 | L'ensemble des caméras disponibles est découvert à l'exécution et publié dans les schémas (énumération) | Un `/dev/videoN` absent ne figure pas dans l'énumération ; la caméra `claw` (index 2) n'est pas annoncée tant que `/dev/video2` est absent | N |
| EF-20 | Une capture renvoie le chemin du fichier, les métadonnées (largeur, hauteur, horodatage) et l'image, avec une taille de réponse bornée | Réponse < 256 Ko ; dimensions et horodatage présents | P |
| EF-21 | Une caméra indisponible produit `E_CAMERA_UNAVAILABLE` avec le périphérique attendu et non une erreur générique | Test avec index inexistant → code et périphérique dans le message | P |
| EF-22 | La détection d'objets renvoie `detection_count`, `inference_ms` et la liste des boîtes au format `vision_msgs` ou équivalent documenté | Le service de détection indisponible produit `E_HW_UNREACHABLE` et non une chaîne d'erreur dans un succès | P |

### 4.6 Bras et pince

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| EF-23 | Les angles articulaires sont validés en cardinalité, en type et en borne avant tout envoi au matériel | Tableau de 3, 4, 6 éléments → 400 `E_INVALID_ARG` ; aucune lecture hors bornes du tableau | P |
| EF-24 | Chaque articulation est bornée dans le schéma et dans la validation | Angle 200° ou −5° → 400 | P |
| EF-25 | La pince accepte exactement deux états et retourne l'angle appliqué | `state` hors `open`/`close` → 400 | S |
| EF-26 | Une pose nommée est identifiée par un identifiant borné, et son contenu est publié en lecture | `/arm/poses` retourne les poses et leurs angles | P |

### 4.7 Audio et signalisation

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| EF-27 | La synthèse vocale n'exécute aucun interpréteur de commandes : l'argument texte est transmis comme un argument de processus | Un texte contenant `;`, `$(`, `"` ou `` ` `` ne produit aucune exécution secondaire (test automatisé) | N |
| EF-28 | Le texte de synthèse est borné en longueur (≤ 300 caractères) et normalisé | Texte de 10 000 caractères → 400 | N |
| EF-29 | La reconnaissance vocale soit renvoie une transcription, soit retourne `E_FEATURE_UNAVAILABLE` avec le prérequis manquant | Aucune réponse de succès ne contient de fichier audio sans transcription | P |
| EF-30 | Les paramètres de LED et de buzzer sont bornés et validés côté serveur | Valeurs hors 0–255 et durée hors 1–5 000 ms → 400 | S |

### 4.8 Énergie et télémétrie

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| EF-31 | La tension est publiée avec son horodatage et un indicateur de péremption | Réponse contient `voltage`, `stamp`, `stale` | P |
| EF-32 | L'état de charge est calculé selon une courbe déclarée et documentée, ou marqué indisponible | Courbe publiée dans le contrat ; à 11,9 V la valeur retournée est reproductible | P |
| EF-33 | La télémétrie agrégée (IMU, vitesse, servos, énergie) est exposée au LLM | `GET /telemetry` atteignable depuis le pont ; réponse conforme au service 8001 | N |

### 4.9 Modes d'exploitation

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| EF-34 | Le mode courant restreint l'ensemble des outils exécutables | Outil hors mode → 403 `E_MODE_FORBIDDEN` avec la liste des outils autorisés | S |
| EF-35 | Le passage de mode exécute ses préconditions (arrêt, position de bras, signalisation) de manière atomique | Transition observée : vitesse nulle et pose appliquée avant retour 200 ; aucune exécution partielle | P |
| EF-36 | Le mode est persistant et son état initial est explicite au démarrage | Après redémarrage, `GET /mode` retourne le mode enregistré ou `standby` selon une règle documentée | N |
| EF-37 | Les routes d'exploitation et de développement (`build`, `test`, maintenance) sont soumises au mode et à l'authentification, ou absentes du service de production | En mode `standby`, `POST /evolution/build` retourne 403 ; en production, la route n'existe pas | N |

### 4.10 Exploitation et cycle de vie

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| EF-38 | `/health` distingue vivacité du processus et disponibilité de la chaîne ROS 2 et du service matériel | Deux champs distincts ; indisponibilité du service 8001 détectée en moins de 2 s | P |
| EF-39 | L'arrêt du service remet les actionneurs en état sûr et publie une vitesse nulle | SIGTERM pendant un mouvement → vitesse nulle observée, code de sortie 0 | N |
| EF-40 | Les fonctions de cartographie (démarrage/arrêt SLAM, sauvegarde, liste, lecture d'image) sont soit exposées avec leur contrat, soit déclarées hors périmètre | Document de périmètre signé ; aucune route du service 8001 sans statut déclaré | N |

## 5. Exigences non fonctionnelles

| ID | Exigence | Critère d'acceptation | État |
|---|---|---|---|
| ENF-01 | Latence d'un outil de lecture : p95 < 150 ms sur le réseau local | Mesure sur 100 appels ; référence constatée 39–51 ms | S |
| ENF-02 | Latence d'acquittement d'une commande d'actionneur : < 100 ms jusqu'à la publication ROS 2 | Mesure instrumentée côté service matériel | P |
| ENF-03 | Concurrence : 8 requêtes simultanées sans erreur ni interblocage ; nombre de connexions simultanées borné | Test de charge à 8 et 32 clients ; aucune réponse tronquée | N |
| ENF-04 | Robustesse : aucune terminaison du processus sur entrée malformée (URL, JSON, corps surdimensionné, en-têtes incohérents) | Campagne de 1 000 requêtes aléatoires, 0 arrêt | N |
| ENF-05 | Intégrité des réponses : toute réponse de taille supérieure à la taille du tampon d'émission est écrite intégralement | Test avec image de 1 Mo ; JSON valide à la réception | N |
| ENF-06 | Mémoire résidente < 150 Mo, charge CPU au repos < 10 % | `systemd-cgtop`, `tegrastats` | Donnée non disponible — non instrumenté |
| ENF-07 | Sécurité réseau : écoute limitée à la boucle locale, ou authentification obligatoire et transport chiffré au-delà | `ss -ltnp` montre 127.0.0.1, ou un appel sans jeton retourne 401 | N |
| ENF-08 | Autorisation par capacité : lecture (télémétrie) séparable de l'actionnement | Deux jetons distincts ; le jeton lecture ne peut pas appeler `SetVelocity` | A |
| ENF-09 | Limitation de débit par client et par outil d'actionnement | 429 au-delà du seuil documenté | A |
| ENF-10 | Journalisation structurée JSON, rotation et purge, compatibles avec une partition à 4,3 Go libres | Volume quotidien mesuré < 50 Mo ; rotation configurée | N |
| ENF-11 | Tests automatisés : contrat (schémas), propriétés (bornes), intégration (matériel simulé), sécurité (injection, authentification) | Chaîne de tests exécutable en une commande, résultat reproductible | N |
| ENF-12 | Couverture de la logique d'adaptation ≥ 70 % | Rapport de couverture | A |
| ENF-13 | Source unique des capacités et des bornes, génération des schémas OpenAI/Anthropic/OpenAPI | Un fichier de définition ; artefacts générés vérifiés par test | N |
| ENF-14 | Portabilité aarch64 / Ubuntu 22.04 / ROS 2 Humble, sans dépendance à un interpréteur de commandes | Build propre et tests verts sur cible | S |

## 6. Contraintes et hypothèses

| ID | Contrainte | Origine |
|---|---|---|
| C-01 | ROS 2 Humble, `ROS_DOMAIN_ID=28` imposé par toutes les unités systemd | [[ros2_graph_clawbot]] |
| C-02 | Aucune source laser : `/scan` absent, aucun paquet lidar installé | [[ERR-2026-11-10-001_absence_topic_scan]] |
| C-03 | Aucune odométrie ni transformation `base_link`/`odom`/`map` dans TF | [[ERR-2026-11-10-003_arbre_tf_incomplet]] |
| C-04 | Partition racine à 97 % : 4,3 Go libres | [[ERR-2026-11-10-002_espace_disque_critique]] |
| C-05 | Lien série `/dev/myserial` à propriétaire unique (`driver_node`, 115 200 Bd) | [[rosmaster_x3_mcu]] |
| C-06 | Énergie : tension seule, pas de jauge système (`/sys/class/power_supply` vide) | [[batterie_principale]] |
| C-07 | Caméras : `/dev/video0` et `/dev/video1` présents, `/dev/video2` absent ; capteur RGB-D Astra Pro+ exploité par le nœud ROS 2 | [[orbbec_astra_pro_plus]] |
| C-08 | Jetson Orin NX 16 Go, mode `MAXN_SUPER`, 8 cœurs | [[jetson_orin_nx]] |
| H-01 | Le LLM appelant est un client réseau authentifié et non hostile ; il peut néanmoins produire des arguments erronés ou extrêmes | Hypothèse de conception |
| H-02 | Un opérateur humain peut atteindre le robot physiquement et couper l'alimentation | Hypothèse d'exploitation |

## 7. Interfaces externes

| Interface | Sens | Format | Statut |
|---|---|---|---|
| HTTP `/tools` | sortie | JSON Schema (OpenAI, Anthropic, raw) | Existant |
| HTTP `/command` | entrée | `{"function","arguments"}` | Existant, à réviser (EF-03, EF-04) |
| HTTP `/mode` | entrée/sortie | `{"mode"}` | Existant |
| HTTP service matériel 8001 | interne | REST FastAPI | Existant |
| ROS 2 `/cmd_vel`, `/servo_ctrl`, `/RGBLight`, `/Buzzer` | sortie | types ROS 2 standard | Existant |
| ROS 2 `/telemetry` (agrégée) | entrée | JSON du service 8001 | Non exposé (EF-33) |

## 8. Critères de recette

Un service est accepté lorsque, dans l'ordre :

1. `GET /tools` et `GET /tools?format=anthropic` valident contre leur schéma et leur cardinalité égale le nombre d'outils implémentés (EF-01).
2. Un appel d'outil de lecture se décode en un seul `jq` (EF-03) et retourne `request_id` (EF-08).
3. Un `SetVelocity` de 1,0 s laisse `/vel_raw` à 0,000 m/s à t = 1,3 s ; un `Stop` concurrent prend effet en moins de 100 ms (EF-11, EF-13).
4. Un texte de synthèse contenant `;` ou `$(` ne crée aucun fichier ni processus secondaire (EF-27).
5. Un appel sans jeton retourne 401 ; un appel depuis une autre machine du réseau local est refusé (ENF-07).
6. 1 000 requêtes malformées n'arrêtent pas le processus (ENF-04) et une réponse de 1 Mo reste un JSON valide (ENF-05).
7. Un `NavigateTo` sans odométrie retourne `E_PREREQ_MISSING` (EF-16).
8. La chaîne de tests complète s'exécute en une commande et retourne le code 0 (ENF-11).

## 9. Matrice de traçabilité

| Défaut constaté | Exigences concernées |
|---|---|
| Aucune authentification, écoute `0.0.0.0`, CORS `*` | EF-37, ENF-07, ENF-08 |
| Exécution de commande arbitraire via `Speak` et `/evolution/build` | EF-27, EF-28, EF-37 |
| Réponse en chaîne JSON doublement encodée | EF-03 |
| `arguments` sous forme de chaîne rejeté | EF-04 |
| Identifiant de corrélation non retourné | EF-08, EF-09 |
| `timeout` inopérant (`std::async` + `wait_for`) | EF-05, ENF-03 |
| Trois jeux de bornes de vitesse | EF-15 |
| `clamped` jamais renvoyé par `/motion` | EF-15, EF-11 |
| Navigation en boucle ouverte sans odométrie | EF-16, EF-17, EF-18 |
| Auto-stop par threads détachés non annulables | EF-11, EF-12 |
| Caméra `claw` annoncée mais absente | EF-19, EF-21 |
| Routes SLAM/cartes/télémétrie non exposées | EF-33, EF-40 |
| Mode non persistant, routes d'exploitation hors mode | EF-36, EF-37 |
| Absence de tests C++, code non versionné | EF-06, ENF-11, ENF-12 |

## 10. Hors périmètre

Le modèle de langage et sa politique de décision ; la qualité de la perception (précision YOLO) ; la mécanique du bras ; la pile SLAM ; la sécurité fonctionnelle certifiée (ISO 13849, ISO 3691-4) — les exigences ci-dessus couvrent la sécurité informatique et l'arrêt sûr, pas la certification.

## 11. Voir aussi

- État constaté du service : [[llm2ros_bridge]]
- Analyse de cohérence et approche cible : [[llm2ros_bridge_coherence_et_approche]]
- Trace de sécurité critique : [[ERR-2026-11-10-004_execution_de_commande_non_authentifiee]]
- Contraintes matérielles : [[rosmaster_x3_mcu]], [[orbbec_astra_pro_plus]], [[batterie_principale]], [[jetson_orin_nx]]
