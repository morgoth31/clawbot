## 1. Architecture du Répertoire Projet

L'organisation des fichiers suit les standards des packages ROS 2 (`colcon`) tout en intégrant une application Web moderne.

```text
ros2_llm_bridge/
├── launch/
│   └── bridge_launch.py          # Lancement coordonné de ROS 2 et de l'API
├── ros2_llm_bridge/
│   ├── __init__.py
│   ├── bridge_node.py            # Nœud ROS 2 (Logic Bridge)
│   ├── api_server.py             # Serveur FastAPI
│   ├── schemas.py                # Modèles Pydantic (Validation LLM)
│   └── llm_handler.py            # Interface avec l'API LLM (OpenAI/Gemini)
├── config/
│   └── params.yaml               # Paramètres ROS et clés API
├── Dockerfile                    # Containerisation (Ubuntu + ROS 2 Humble/Jazzy)
├── docker-compose.yml            # Orchestration des services
├── package.xml                   # Dépendances ROS 2
└── setup.py                      # Configuration du package Python

```

---

## 2. Description des Fichiers Clés

### 2.1 `bridge_node.py` (Le Cœur Robotique)

Ce fichier contient une classe héritant de `rclpy.node.Node`. Elle encapsule tous les clients de services, les éditeurs de topics et les clients d'actions. Son rôle est de traduire les requêtes Python standards en messages middleware DDS.

### 2.2 `api_server.py` (L'Interface Synchrone/Asynchrone)

Il initialise FastAPI avec un cycle de vie (`lifespan`) gérant le thread de l'exécuteur ROS 2. Il définit les routes POST que le LLM utilisera comme outils.

### 2.3 `schemas.py` (La Rigueur des Données)

Contient les classes `BaseModel` de Pydantic. Ces classes servent de source de vérité pour la génération automatique du schéma JSON fourni au LLM pour le *Function Calling*.

### 2.4 `llm_handler.py` (La Logique Décisionnelle)

Gère l'envoi de la requête utilisateur au LLM, reçoit l'appel de fonction, et exécute la fonction Python correspondante qui communique avec le nœud ROS 2.

---

## 3. "Stories" de Développement : Étapes de Réalisation

### Étape 1 : Initialisation du Pont Middleware (Story : "The Silent Node")

L'objectif est de créer un nœud ROS 2 capable de fonctionner de manière autonome dans un thread Python sans bloquer l'exécution d'autres processus.

* **Action** : Implémenter le `MultiThreadedExecutor` dans `api_server.py`.
* **Validation** : Lancer le serveur et vérifier que le nœud est visible via la commande `ros2 node list` alors que l'API répond aux requêtes HTTP.

### Étape 2 : Abstraction des Commandes Robotiques (Story : "Typed Commands")

Il s'agit de définir les capacités du robot de manière stricte.

* **Action** : Créer les modèles Pydantic pour chaque mouvement (ex: `MoveTo(x, y, theta)`). Développer les méthodes asynchrones dans le nœud ROS 2 utilisant `asyncio.wrap_future` pour attendre les réponses des services ROS.
* **Validation** : Envoyer une requête `curl` au serveur FastAPI et observer le mouvement physique ou simulé du robot.

### Étape 3 : Intégration du LLM et Function Calling (Story : "The Reasoning Brain")

Connecter l'intelligence artificielle aux commandes définies à l'étape précédente.

* **Action** : Configurer le client LLM pour utiliser les schémas de `schemas.py` comme outils disponibles. Implémenter la boucle de rétroaction : l'utilisateur parle en langage naturel  le LLM choisit la fonction  le pont exécute  le résultat est renvoyé au LLM pour confirmation.
* **Validation** : Envoyer une commande vague (ex: "Avance de deux mètres et tourne à gauche") et vérifier que le LLM appelle les fonctions avec les bons paramètres numériques.

### Étape 4 : Sécurisation et Conteneurisation (Story : "Safe Deployment")

Assurer la portabilité et la sécurité du système.

* **Action** : Écrire le `Dockerfile` basé sur une image `ros:humble-ros-base`. Intégrer une couche de validation de sécurité qui intercepte les commandes du LLM avant exécution pour vérifier qu'elles ne violent pas les limites physiques (Geofencing).
* **Validation** : Déploiement via `docker-compose` sur une cible Linux Ubuntu, garantissant que toutes les dépendances (FastAPI, rclpy, bibliothèques LLM) sont isolées et fonctionnelles.

---

## 4. Méthode de Détermination des Erreurs

Si le système ne répond pas, la méthode de diagnostic rigoureuse est la suivante :

1. **Niveau Transport** : Vérifier le domaine ROS (`ROS_DOMAIN_ID`) et la connectivité DDS via `ros2 topic echo`.
2. **Niveau API** : Consulter les logs Uvicorn pour détecter des exceptions de type `FutureTimeoutError`.
3. **Niveau LLM** : Analyser les "raw tool calls" du LLM pour identifier des erreurs de typage JSON ou des hallucinations de paramètres.



---

## 1. Documentation Technique et Auto-générée

La documentation ne doit pas être un simple fichier texte, mais faire partie intégrante du flux de données.

* **Documentation des API (Swagger/OpenAPI) :** Puisque vous utilisez FastAPI, assurez-vous que chaque route dans `api_server.py` est documentée avec des `Summary`, `Description` et `Response Models`. Cela permet de tester les endpoints sans client externe via `/docs`.
* **Contrats d'Interface LLM :** Documentez les classes Pydantic dans `schemas.py` en utilisant l'attribut `Field(description="...")`. Cette description est cruciale car elle est directement injectée dans le prompt système du LLM pour réduire les hallucinations lors du *Function Calling*.
* **Docstrings Normalisés :** Appliquez le standard **Google Style** ou **NumPy Style** pour toutes les fonctions dans `bridge_node.py` et `llm_handler.py`.
* *Tâche précise :* Utiliser un outil comme `pydocstyle` pour vérifier la conformité.



---

## 2. Stratégie de Test Multi-Niveaux

Dans un environnement ROS 2, les tests doivent couvrir à la fois la logique métier Python et les interactions entre les nœuds.

### 2.1 Tests Unitaires (Logique Pure)

* **Cible :** `llm_handler.py` et `schemas.py`.
* **Action :** Utiliser `pytest` pour valider que les modèles Pydantic rejettent les données malformées (ex: coordonnées négatives si interdites).
* **Mocking :** Utiliser `unittest.mock` pour simuler les réponses de l'API OpenAI/Gemini afin de ne pas consommer de jetons lors des tests.

### 2.2 Tests d'Intégration (Middleware)

* **Cible :** `bridge_node.py`.
* **Action :** Implémenter des tests via `launch_testing`. Ce framework ROS 2 permet de lancer le nœud et de vérifier qu'il publie correctement sur les topics ou répond aux services après avoir reçu une commande de l'API.
* **Validation :** Vérifier que les appels asynchrones via `asyncio.wrap_future` gèrent correctement les timeouts si le robot ne répond pas.

### 2.3 Tests de Charge et de Concurrence

* **Action :** Simuler plusieurs requêtes HTTP simultanées sur `api_server.py` pour valider que le `MultiThreadedExecutor` de ROS 2 traite les requêtes sans interblocage (*deadlock*).

---

## 3. Qualité de Code et Analyse Statique

L'utilisation de Linux Ubuntu facilite l'intégration d'outils de *linting* dans votre workflow.

* **Typage Statique avec Mypy :** Étant donné que ROS 2 utilise intensivement les types dynamiques en Python, forcer le typage avec `mypy` dans tout le projet réduit drastiquement les erreurs au runtime.
* **Formatage Automatique :** Intégrez `ruff` ou `black` pour garantir une structure de code uniforme, facilitant la lecture pour d'autres développeurs.
* **Gestion des Dépendances :** Utilisez un fichier `requirements.txt` ou `pyproject.toml` en complément du `package.xml` pour isoler les dépendances Python (FastAPI, LangChain, etc.) des dépendances système ROS.

---

## 4. Tâches Spécifiques aux "Stories" de Développement

Voici les tâches de maintenabilité appliquées à vos étapes de réalisation :

### Pour l'Étape 1 (The Silent Node)

* **Gestion du cycle de vie :** Implémenter un mécanisme de *Graceful Shutdown* dans `api_server.py`. Assurez-vous que `node.destroy_node()` et `rclpy.shutdown()` sont appelés proprement lors de l'arrêt du conteneur Docker pour libérer les ressources DDS.

### Pour l'Étape 2 (Typed Commands)

* **Mapping d'Exceptions :** Créer un gestionnaire d'exceptions global qui traduit les erreurs ROS (ex: `ServiceNotFound`) en codes d'erreur HTTP explicites (ex: `503 Service Unavailable`) pour l'API.

### Pour l'Étape 3 (The Reasoning Brain)

* **Observabilité et Logs :** Implémenter un système de logging structuré (via `logging` de Python ou le logger ROS). Chaque décision prise par le LLM (choix de fonction, arguments) doit être enregistrée avec un `correlation_id` pour tracer une action de l'utilisateur jusqu'au mouvement du robot.

### Pour l'Étape 4 (Safe Deployment)

* **Health Checks Docker :** Ajouter une instruction `HEALTHCHECK` dans le `Dockerfile` qui interroge un endpoint `/health` de FastAPI. Cela permet à Docker Compose de savoir si le pont est réellement prêt à recevoir des commandes.
* **Variables d'Environnement :** Externaliser les clés API et les paramètres réseau dans un fichier `.env` non versionné, géré par `Pydantic Settings`.

---

## 5. Résumé des tâches par fichier

| Fichier | Tâche de Maintenabilité | Outil Recommandé |
| --- | --- | --- |
| `schemas.py` | Validation stricte et documentation des schémas JSON. | `Pydantic` |
| `bridge_node.py` | Tests d'intégration avec simulateur (Gazebo/Ignition). | `launch_testing` |
| `api_server.py` | Monitoring des threads et documentation OpenAPI. | `FastAPI` / `Uvicorn` |
| `Dockerfile` | Optimisation via des *multi-stage builds* pour réduire la taille. | `Docker` |
| `params.yaml` | Validation des types de paramètres ROS. | `ros2 param` |

Souhaitez-vous que je rédige un exemple de test d'intégration utilisant `launch_testing` pour valider la communication entre votre serveur FastAPI et votre nœud ROS 2 ?