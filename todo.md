
## 1. Modélisation et Architecture Cinématique

La validation du modèle physique est le prérequis avant toute intégration logicielle.

* **Validation du format URDF / Xacro :** Le fichier décrit les liens physiques (`links`) et les articulations (`joints`).
* *Méthode de vérification :* Générer l'URDF à partir du Xacro, puis exécuter l'outil de parsing standard. La commande `check_urdf mon_robot.urdf` validera la syntaxe et la hiérarchie.
* *Vérification des transformations (TF) :* Lancer un nœud `robot_state_publisher` couplé à `joint_state_publisher_gui`. Utiliser l'outil `tf2_tools` pour générer le graphe des transformations (`ros2 run tf2_tools view_frames`). L'arbre généré doit être continu, de la racine (`base_link`) jusqu'aux effecteurs (`camera_link`, `gripper_link`).



---

## 2. Actionneurs et Contrôle

Cette section englobe la base mobile et le bras manipulateur.

### 2.1. Nœud Cinématique Mecanum

* **Informations de sortie requises :** Le nœud doit publier la vitesse angulaire individuelle des quatre roues, la vitesse globale du robot (vecteur de translation $V_x$, $V_y$ et rotation $\omega$), ainsi que l'odométrie estimée (position absolue $X, Y, \theta$ par rapport au repère de départ).
* **Procédure de test et de calibration :**
1. **Sur cales (Boucle ouverte) :** Envoyer des commandes de vitesse angulaire positives à chaque moteur individuellement. Vérifier que le sens de rotation correspond au modèle cinématique direct et que les encodeurs remontent des valeurs cohérentes.
2. **Au sol (Validation cinématique) :** Commander des translations pures (axe X, puis axe Y) et une rotation pure sur place. Mesurer la distance réelle parcourue.
3. **Calibration :** Calculer le facteur de correction pour compenser le glissement inhérent aux roues Mecanum et ajuster les rayons théoriques des roues dans la matrice cinématique.



### 2.2. Bras Manipulateur et Pince

* **Intégration de MoveIt2 :** L'utilisation d'une librairie comme MoveIt2 est impérative. MoveIt2 gère la cinématique inverse (IK), la planification de trajectoire dans l'espace des configurations, et l'évitement d'obstacles en temps réel (via les octomaps générés par les capteurs 3D). Développer ces algorithmes de zéro est inefficace.
* **Procédure de calibration :**
1. Définir les limites articulaires (position, vitesse, effort) dans le fichier URDF.
2. Identifier les "zéros" (home position) de chaque moteur.
3. Pour la pince (gripper), étalonner le retour de force pour déterminer les seuils de détection de préhension (fermeture à vide vs fermeture sur objet).



---

## 3. Perception, Vision et Cartographie

L'acquisition et le traitement des données capteurs nécessitent une gestion stricte de la bande passante et des ressources de calcul.

### 3.1. Pipeline Caméra Standard (nvargus) & YOLO

* **Acquisition nvargus :** L'utilisation de `nvarguscamerasrc` implique un processeur NVIDIA Jetson. L'acquisition doit se faire via un pipeline GStreamer optimisé matériellement pour réduire la latence CPU. Le flux brut en NV12 doit être converti en BGR pour le traitement algorithmique.
* **Intégration YOLO :** Le modèle YOLO doit être encapsulé dans un nœud dédié qui souscrit au flux d'images traité. En sortie, le nœud doit publier les boîtes englobantes (`BoundingBoxes`) accompagnées de leur score de confiance et de leur classe sémantique.

### 3.2. Caméra 3D Orbbec

* **Cartographie et Navigation Autonome :** L'utilisation de cette caméra pour la navigation autonome et la cartographie 3D est standard et parfaitement viable.
* **Modules adaptés :**
* **Module de profondeur (Depth) :** Indispensable. Il génère la carte de profondeur qui, convertie en LaserScan 2D ou projetée dans un plan, alimente les *costmaps* de navigation (pour l'évitement d'obstacles local).
* **Génération de Nuage de Points (Pointcloud) :** La combinaison du flux de profondeur et du flux RGB permet de générer un `PointCloud2` colorisé. Ce format est requis pour les algorithmes de SLAM 3D (comme RTAB-Map).
* **Module IMU interne :** Si la caméra Orbbec en possède un, ses données doivent être fusionnées via un filtre de Kalman étendu (EKF) avec l'odométrie des roues pour stabiliser la carte 3D.



---

## 4. Frontend de Débogage

Pour un affichage en temps réel sans surcharger le système embarqué, une architecture découplée est requise.

* **Choix technologique :** Il est possible de développer une interface web sur mesure utilisant JavaScript et HTML, communiquant avec le middleware robotique via des WebSockets (ex: `rosbridge_suite`). Alternativement, des outils natifs configurables comme Foxglove Studio permettent d'agréger toutes ces données nativement sans développement frontend supplémentaire.
* **Données à intégrer au dashboard :**
* **Navigation :** Carte globale (Map) superposée avec la pose du robot (TF `map` -> `base_link`) et les données Lidar brutes (LaserScan).
* **Vision :** Flux vidéo compressé de la caméra principale et/ou YOLO.
* **Télémétrie Bras :** Position articulaire actuelle, orientation spatiale de l'effecteur final (TF `base_link` -> `gripper_link`), retour de force des moteurs, état d'ouverture de la pince.
* **Centrale Inertielle (IMU) :** Orientation spatiale (quaternion converti en angles d'Euler RPY), vecteurs de vitesse angulaire et d'accélération linéaire.
* **Base Mobile :** Vitesse de consigne vs vitesse réelle, régime de chaque roue.



---

Souhaites-tu que je détaille le pipeline GStreamer précis pour optimiser l'acquisition nvargus, ou préfères-tu une méthode pour configurer l'assistant MoveIt2 pour ton bras manipulateur ?