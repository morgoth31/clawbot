---
title: "Documentation constructeur Yahboom — dépôt ROSMASTERX3-PLUS"
date: "2026-11-10T11:33:00+01:00"
author: "Hermes Agent"
tags: [software, documentation, yahboom, rosmaster, reference, constructeur, veille]
status: actif
---

# Documentation constructeur Yahboom — dépôt ROSMASTERX3-PLUS

Référence externe officielle de la plateforme : `https://github.com/YahboomTechnology/ROSMASTERX3-PLUS`. Elle documente le robot **ROSMASTER X3 PLUS**, dont le Clawbot X3 est une instance (Jetson Orin NX, châssis mecanum, bras 6 axes, Astra Pro+, lidar YDLIDAR). Retour à l'[[index]].

## 1. État du dépôt

| Élément | Valeur | Source |
|---|---|---|
| URL | `https://github.com/YahboomTechnology/ROSMASTERX3-PLUS` | — |
| Branche | `main`, unique | API GitHub `git/trees/main` |
| Dernier commit | `9732c62` « Add files via upload », 2025-08-28 | page GitHub |
| Commits | 155 | page GitHub |
| Étiquettes / releases | aucune | page GitHub |
| Volume | 351 fichiers, 391,2 Mo, dont 340 PDF | API GitHub |
| Fichiers texte | `README.md`, 5 `.txt` (liens vidéo, annexe, précautions lidar) | API GitHub |
| Licence | aucune licence déclarée dans le dépôt | arborescence : ni `LICENSE`, ni mention dans `README.md` |

Conséquence pratique : les PDF peuvent être lus et cités, mais aucun droit de redistribution n'est accordé explicitement. Les pages de cette base reformulent des faits techniques et renvoient au dépôt, elles ne recopient pas les documents.

## 2. Structure

Vingt chapitres numérotés, plus une arborescence dupliquée pour ROS 1 :

| Chapitre | Contenu | Volume |
|---|---|---|
| `01.Preparation and First Trial` | câblage, précautions batterie, premier démarrage | 4 PDF |
| `02.Assembly steps` | lien YouTube uniquement | — |
| `03.Remote control course` | application mobile, radiocommande avion, manette USB | 3 PDF |
| `04.Hardware course` | carte d'extension V1.0/V3.0, STM32, GPIO, série, CAN, SBUS, moteurs, encodeurs, IMU ICM20948, PID, cinématique | 18 PDF |
| `05.Basic course` | firmware MCU, désactivation de l'auto-démarrage, bibliothèque `Rosmaster_Lib`, buzzer, PWM, RGB, moteurs | 9 PDF |
| `06.Linux operating system` | machine virtuelle, réseau, IP statique, hotspot | 12 PDF |
| `07.Docker-pi5` | Docker sur Raspberry Pi 5 | 7 PDF |
| `08.ROS basic course` | ROS 1 : topics, services, actions, messages, launch | 22 PDF |
| `09.OpenCV courses` | OpenCV, MediaPipe, nuages de points | 12 PDF |
| `10.Robot control course` | PID, publication d'état, clavier, manette, estimation d'état, calibration, URDF | 8 PDF |
| `11.Depth camera course` | SDK Astra, étalonnage, suivi, RTAB-Map, ORB-SLAM2 | 9 PDF |
| `12.Lidar course` | principes, cartographie gmapping/hector/karto/cartographer, AMCL, navigation | 14 PDF |
| `13.Multi-robot control course` | manette, navigation et formation multi-robots | 4 PDF |
| `14.Deep learning courses` | KNN, TensorFlow, PyTorch, YOLOv5, TensorRT | 6 PDF |
| `15.Voice control courses` | module vocal (ancienne et nouvelle version) | 11 PDF |
| `16.Robotic arm control course` | MoveIt, MediaPipe, gestes, tri de blocs | 15 PDF |
| `17.Voice control robotic arm course` | bras piloté à la voix | 5 PDF |
| `18.Model training Autopilot` | collecte, entraînement YOLOv5, TensorRT | 8 PDF |
| `19.For Jetson Orin-ROS1` | duplication complète des chapitres 03 à 18 pour ROS 1 sur Orin | 142 PDF |
| `20.LLM tutorial` | Ollama, Open WebUI, Llama3, Qwen2, Phi-3, DeepSeek-R1 sur Orin NX/Nano | 31 PDF |

Le dépôt ne publie que des PDF et des liens : le code, les images d'installation, les `.hex` de firmware et les archives de cours sont renvoyés vers un dossier Google Drive (`Annex_Download_Link/Download link.txt`). Aucun code source du firmware STM32 n'est présent.

## 3. Ce qui s'applique à ce robot

Le Clawbot X3 embarque **ROS 2 Humble** sur Ubuntu 22.04, alors que la documentation constructeur décrit **Ubuntu 18.04 + ROS Melodic** (`README.md`, §ROS operating system). Les commandes `roslaunch`/`rostopic` du dépôt ne sont donc pas transposables telles quelles ; les faits matériels et les protocoles le sont.

| Chapitre | Apport retenu dans cette base | Page |
|---|---|---|
| `01` câblage, batterie | tensions, précautions de charge, ordre de mise sous tension | [[batterie_principale]] |
| `04` carte V3.0, moteurs, encodeurs, IMU | inventaire des connecteurs, affectation M1–M4 / TIM2-3-4-5, ICM20948 en SPI2, PID incrémental | [[rosmaster_x3_mcu]] |
| `05` firmware, `Rosmaster_Lib` | sémantique de l'API (rapport automatique 4 × 10 ms, bornes de vitesse, IDs de servo) et procédure de flashage | [[rosmaster_x3_mcu]], [[mise_a_jour_firmware_carte_rosmaster]] |
| `10` estimation d'état, calibration | référence pour l'odométrie du nœud de conduite | [[yahboomcar_bringup_driver_node]] |
| `11` caméra Astra | famille Astra/Astra Pro/Astra Pro+, découpage UVC + profondeur, étalonnage | [[orbbec_astra_pro_plus]] |
| `12` lidar TG (4ROS) | paramètres de référence du `TG.launch`, principe TOF | [[ydlidar_tg30]] |
| `12` précautions cartographie | robot immobile 5 s après mise sous tension pour l'initialisation du gyroscope, sinon la carte tourne sur elle-même dans RViz | [[ros2_nav_stack]] |
| `20` LLM sur Orin | Ollama, Open WebUI, modèles quantifiés pour Orin NX | [[llm2ros_bridge]] (contexte) |

## 4. Ce que le dépôt n'apporte pas

- **Aucune procédure ROS 2** : ni `ros2 launch`, ni nœud `ydlidar_ros2_driver`, ni `astra_camera` version ROS 2 ; les chemins et paquets installés sur ce robot viennent de l'image fournie, pas des PDF.
- **Aucune mesure sur ce robot** : aucune valeur de cette base n'est reprise des PDF sans vérification sur le poste. Une valeur constructeur non vérifiée est citée comme telle.
- **Aucune licence** : voir §1.
- **Bras 6 axes** : le dépôt documente le bras et MoveIt, mais la présence physique du bras sur ce châssis n'est pas établie par une mesure ; l'URDF chargé décrit `arm_joint1` à `arm_joint5` et `grip_joint`, ce qui ne prouve pas le montage.
- **Module vocal** : documenté, non identifié sur ce robot (l'interface `1a86:7522` sans nœud TTY reste non attribuée, cf. [[rosmaster_x3_mcu]] §1).

## 5. Comment citer une source constructeur dans cette base

Toute affirmation issue du dépôt porte le chemin exact du PDF ou du fichier, par exemple `04.Hardware course/1. About expansion board/1.About expansion boardV3.0.pdf`. Le chemin permet de retrouver la page dans le dépôt sans stocker 391 Mo localement. Quand la valeur constructeur et la mesure divergent, **la mesure est écrite et l'écart est documenté**, comme pour [[ydlidar_tg30]] §7.

## 6. Voir aussi

- Carte de commande : [[rosmaster_x3_mcu]]
- Lidar : [[ydlidar_tg30]]
- Caméra : [[orbbec_astra_pro_plus]]
- Nœud de conduite : [[yahboomcar_bringup_driver_node]]
- Chaîne de navigation : [[ros2_nav_stack]]
- Procédure de flashage MCU : [[mise_a_jour_firmware_carte_rosmaster]]
