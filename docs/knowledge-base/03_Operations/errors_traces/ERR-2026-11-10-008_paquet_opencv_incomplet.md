---
title: "ERR-2026-11-10-008 — paquet OpenCV de développement incohérent, compilation SLAM"
date: "2026-11-10T12:25:00+01:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, opencv, cmake, build, slam, jetpack]
status: ouvert
---

# ERR-2026-11-10-008 — paquet OpenCV de développement incohérent, compilation SLAM

| Champ | Valeur |
|---|---|
| Identifiant | `ERR-2026-11-10-008` |
| Horodatage de détection | 2026-11-10T11:41:00+01:00 (CET) |
| Domaine ROS 2 | 28 (sans objet pour la compilation) |
| Topics concernés | Aucun |
| Composant lié | [[ros2_nav_stack]], paquet `yahboomcar_slam` |
| Gravité d'exploitation | Empêche la reconstruction de la chaîne SLAM ; n'affecte pas les nœuds en service |
| Statut | validé — compilation réparée ; paquet NVIDIA toujours incomplet (contourné par configuration) |
| Mitigation appliquée | Préfixe OpenCV 4.5.4 extrait des `.deb` Ubuntu dans `/opt/opencv-4.5.4-dev`, sélectionné par `~/.colcon/defaults.yaml` |

## 1. Nature de l'échec

La reconstruction propre du workspace `yahboomcar_ws` échoue sur `yahboomcar_slam` :

```
CMake Error at /usr/lib/cmake/opencv4/OpenCVModules.cmake:172 (message):
  The imported target "opencv_core" references the file
     "/usr/lib/libopencv_core.so.4.8.0"
  but this file does not exist.
```

Le paquet `libopencv-dev` fourni par le dépôt NVIDIA JetPack (`4.8.0-1-g6371ee1`) installe des configurations CMake et des liens symboliques (`/usr/lib/libopencv_core.so` → `libopencv_core.so.408`) dont **les bibliothèques partagées sont absentes** : aucune `libopencv_core.so.408` sur le disque. Les bibliothèques réellement présentes sont celles d'Ubuntu, version `4.5.4d`, dans `/usr/lib/aarch64-linux-gnu/`, et c'est cette version que lie `cv_bridge` :

```
$ ldd /opt/ros/humble/lib/libcv_bridge.so | grep opencv
  libopencv_imgcodecs.so.4.5d => /lib/aarch64-linux-gnu/libopencv_imgcodecs.so.4.5d
  libopencv_core.so.4.5d      => /lib/aarch64-linux-gnu/libopencv_core.so.4.5d
```

## 2. Preuves

```
$ cmake -S . -B build2 -DOpenCV_DIR=/usr/lib/cmake/opencv4
CMake Error at /usr/lib/cmake/opencv4/OpenCVModules.cmake:172 (message):
  The imported target "opencv_core" references the file
     "/usr/lib/libopencv_core.so.4.8.0" but this file does not exist.

$ grep -o 'IMPORTED_LOCATION_RELEASE "[^"]*"' /usr/lib/cmake/opencv4/OpenCVModules-release.cmake | head -2
IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libopencv_core.so.4.8.0"
IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libopencv_flann.so.4.8.0"

$ ls -l /usr/lib/libopencv_core.so
lrwxrwxrwx 1 root root 21 Aug 29  2023 /usr/lib/libopencv_core.so -> libopencv_core.so.408
$ ls /usr/lib/libopencv_core.so.408
ls: cannot access '/usr/lib/libopencv_core.so.408': No such file or directory
```

Tentatives de correction de l'état des paquets, toutes non abouties :

| Tentative | Résultat |
|---|---|
| Réinstallation de `libopencv-dev` (4.8, dépôt NVIDIA) | inchangé : mêmes fichiers CMake, toujours sans bibliothèques |
| `apt-get install libopencv-dev=4.5.4+dfsg-9ubuntu4` | `dpkg` refuse : le paquet NVIDIA `libopencv-dev` **est en conflit** avec `libopencv-core-dev`, et `opencv-licenses` possède déjà `/usr/share/licenses/opencv4/SoftFloat-COPYING.txt` |
| `dpkg -r --force-depends libopencv-dev opencv-licenses` puis installation 4.5.4 | `apt-get -f install` réinstalle **la version NVIDIA 4.8**, seule candidate (priorité 600 du dépôt JetPack) et exigée par `ros-humble-cv-bridge` |

## 3. Actions de mitigation

Premier contournement essayé puis abandonné : compiler contre OpenCV 4.10 installé dans `/usr/local`. Le paquet se construit, mais `ldd` montre alors **deux** jeux de bibliothèques dans le même exécutable (`libopencv_core.so.4.5d` par `cv_bridge`, `libopencv_core.so.410` par le paquet SLAM), avec des types `cv::Mat` qui traversent la frontière : mélange d'ABI non acceptable pour un nœud de navigation.

Solution retenue — fournir à CMake une installation OpenCV 4.5.4 complète, identique à celle que lie `cv_bridge` :

| Horodatage | Action | Résultat mesuré |
|---|---|---|
| 2026-11-10T12:40:00+01:00 | `apt-get download` des 19 paquets `libopencv-*-dev` en version `4.5.4+dfsg-9ubuntu4` (13,5 Mo) puis `dpkg -x` dans `/opt/opencv-4.5.4-dev` | en-têtes et configurations CMake 4.5.4 disponibles hors gestionnaire de paquets, sans conflit |
| 2026-11-10T12:42:00+01:00 | Liens symboliques vers les bibliothèques système `libopencv_*.so.4.5.4d` (54 liens) dans le préfixe | `find_package(OpenCV)` renvoie `OpenCV 4.5.4 at /opt/opencv-4.5.4-dev/...` |
| 2026-11-10T12:45:00+01:00 | Reconstruction de `yahboomcar_slam`, `yahboomcar_KCFTracker`, `yahboomcar_point` avec `-DOpenCV_DIR=/opt/opencv-4.5.4-dev/...` | 3 paquets compilés ; `ldd` sur `pointcloud_mapping` ne montre plus que `libopencv_core.so.4.5d` |
| 2026-11-10T12:48:00+01:00 | `~/.colcon/defaults.yaml` fixe cet `OpenCV_DIR` pour tous les builds de l'utilisateur | un `colcon build` sans argument reproduit la même configuration |
| 2026-11-10T12:50:00+01:00 | `colcon build` complet du workspace | 22 paquets, 0 échec |

## 4. Conditions de clôture

1. `colcon build` dans `~/yahboomcar_ros2_ws/yahboomcar_ws` termine sans échec : **satisfaite** (22 paquets).
2. `ldd` sur les exécutables de `yahboomcar_slam` ne référence qu'une seule version d'OpenCV, celle de `cv_bridge` : **satisfaite** (`libopencv_core.so.4.5d` uniquement).
3. Le contournement survit à une remise à zéro du workspace (`rm -rf build install`) : **à confirmer** — `~/.colcon/defaults.yaml` s'applique, mais le préfixe `/opt/opencv-4.5.4-dev` doit être recréé si `/opt` est réinitialisé ; les `.deb` sources ne sont pas conservés.

Le défaut de fond n'est pas corrigé : le paquet `libopencv-dev` du dépôt JetPack reste inutilisable et toute réinstallation du système recréera le problème. Le corriger proprement suppose de remplacer ce paquet par la version Ubuntu (`4.5.4`), ce que `apt` refuse aujourd'hui à cause du conflit `libopencv-dev` / `libopencv-core-dev` et du fichier de licence partagé avec `opencv-licenses`.

## 5. Voir aussi

- Chaîne de navigation concernée : [[ros2_nav_stack]]
- Graphe et nœuds : [[ros2_graph_clawbot]]
- Journal de la session : [[index]]
