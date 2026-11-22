# Candidats à la purge — 2026-11-22 (P02)

**APPLIQUÉ le 2026-11-22 à 13:07, après accord de l'opérateur** (« ok pour les
deux »). Résultat : disque de 117 Go / 84 % à **91 Go / 66 %**, soit ≈ 26 Go
libérés. Détail de l'application en fin de document. Les lignes 8 à 10 n'ont pas
été exécutées (voir « Non exécuté »). Disque au moment de la mesure : `/dev/nvme0n1p1` 147 Go,
117 Go utilisés, 24 Go libres (**84 %**), plus gros consommateur =
`/home/jetson` 23 Go, puis les images Docker (34,9 Go, hors /home).

Commandes de mesure : `df -h /`, `du -xh --max-depth=2 /home/jetson /var/log`,
`journalctl --disk-usage`, `docker system df`, `du -sh` par workspace.

## Tableau des candidats

| # | Chemin | Taille | Risque | Commande proposée |
|---|---|---|---|---|
| 1 | Images Docker non référencées (7 images, 34,9 Go au total ; 26,77 Go récupérables) : `yahboomtechnology/ros-noetic:3.0.5` 14,9 Go, `tiryoh/ros2-desktop-vnc:foxy` 7,75 Go, `clawbot-llm_bridge` 857 Mo, `ros2_llm_bridge-llm_bridge` 753 Mo, `clawbot-clawbot_monitoring` 273 Mo | **26,8 Go** | moyen : deux conteneurs tournent (`searxng`, `charles-dashboard` sur `ros-foxy-orbslam2`), ils sont épargnés par `prune -a` ; `ros-noetic` et `ros-foxy-orbslam2` servent peut-être à d'autres projets | `docker image prune -a --filter "until=720h"` puis `docker builder prune` |
| 2 | `/var/cache/apt` (archives .deb) | 1,3 Go | nul : régénéré au besoin | `sudo apt-get clean` |
| 3 | Journal systemd | 289,9 Mo | faible : perd les entrées au-delà de la rétention choisie | `sudo journalctl --vacuum-size=100M` |
| 4 | `/home/jetson/.hermes/cache/uv` + `pnpm` | 721 Mo | faible : caches de gestionnaires de paquets, retéléchargés | `rm -rf ~/.hermes/cache/uv/* ~/.hermes/cache/pnpm/*` |
| 5 | `/home/jetson/.ros/rtabmap_slam3d.db` + `rtabmap.db` | 211 Mo | moyen : cartes 3D d'anciennes sessions rtabmap ; aucun service actif ne les lit (`clawbot-slam` utilise slam_toolbox) | `rm ~/.ros/rtabmap*.db` après confirmation qu'aucune carte n'est à archiver |
| 6 | `/home/jetson/.ros/log` | 51 Mo | nul : journaux de sessions ROS passées | `rm -rf ~/.ros/log/*` |
| 7 | `/home/jetson/clawbot/build` + `log` | 159 Mo | faible : reconstruit par `colcon build` (l'`install/` déployé n'est pas touché) | `rm -rf /home/jetson/clawbot/build /home/jetson/clawbot/log` |
| 8 | `/home/jetson/snap/chromium` | 300 Mo | moyen : application snap ; à retirer seulement si inutilisée | `snap remove chromium` (si confirmé inutilisé) |
| 9 | `/home/jetson/.cache/ms-playwright` | 327 Mo | moyen : navigateurs du profil Hermes « browser » ; réinstallés à la demande | `rm -rf ~/.cache/ms-playwright` (si l'outil navigateur n'est pas utilisé) |
| 10 | `/tmp` | 48 Mo | nul | `rm -rf /tmp/*` (hors fichiers en cours d'usage) |

**Gain total estimé : ≈ 29,4 Go** (dont 26,8 Go sur les seules images Docker),
soit un disque ramené d'environ 84 % à 64 %.

## Ne pas toucher (constaté déployé)

| Chemin | Taille | Raison |
|---|---|---|
| `/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install` | 304 Mo | c'est l'installation que lance `ros2-driver-node.service` (pilote du châssis) |
| `/home/jetson/yahboomcar_ros2_ws/software/library_ws/install` | 466 Mo | c'est l'installation d'`astra_camera`, `ydlidar_ros2_driver` et `robot_localization` |
| `/home/jetson/yolov5_env` | 2,9 Go | environnement Python de `yolo_service.py` (port 8003) |
| `/home/jetson/clawbot/install` | 263 Mo | installation en service (pont C++, interfaces, nœuds maison) |
| `/home/jetson/.local/lib` | 3,6 Go | paquets Python système, dont `fastapi`, `uvicorn`, `pytest` |

## Ordre proposé (après accord)

1. `sudo apt-get clean` et `sudo journalctl --vacuum-size=100M` — sans effet sur le robot.
2. `docker image prune -a --filter "until=720h"` — vérifier ensuite `docker ps` (2 conteneurs attendus).
3. Purges 4 à 7 — sans effet sur le robot, `build/` reconstruit par colcon.
4. 8 et 9 : seulement si l'opérateur confirme que Chromium snap et les navigateurs
   Playwright ne servent pas.

## Application — 2026-11-22 13:07

| Étape | Commande | Résultat mesuré |
|---|---|---|
| 1 | `sudo apt-get clean` | archives .deb supprimées |
| 2 | `sudo journalctl --vacuum-size=100M` | **195,7 Mo** libérés |
| 3 | `docker image prune -a -f --filter "until=720h"` | **22,66 Go** ; l'image `ros2_llm_bridge-llm_bridge` (20621c37) supprimée |
| 3 bis | `docker builder prune -f` | **284,7 Mo** de cache de construction |
| 4 | `rm -rf ~/.hermes/cache/{uv,pnpm}/*` | 721 Mo |
| 5 | `rm ~/.ros/rtabmap.db ~/.ros/rtabmap_slam3d.db` | **220,7 Mo** (46,8 + 173,9) |
| 6 | `rm -rf ~/.ros/log/*` | 51 Mo |
| 7 | `rm -rf /home/jetson/clawbot/{build,log}` | 159 Mo |

Disque : **117 Go → 91 Go utilisés**, 24 Go → **49 Go libres**, 84 % → **66 %**
(≈ 26 Go libérés). Les deux conteneurs actifs (`searxng`, `charles-dashboard`)
n'ont pas été touchés ; `docker ps` toujours à 2.

Contrôle après purge : aucune unité du robot en échec, `clawbot-sentinel`,
`clawbot-director`, `clawbot-safety-arbitrator` et `ros2-driver-node` actifs.

## Non exécuté (volontairement)

| # | Objet | Raison |
|---|---|---|
| 8 | `snap remove chromium` | « ok pour les deux » ne dit pas que Chromium est inutilisé ; 300 Mo ne justifient pas de retirer une application sans confirmation explicite |
| 9 | `~/.cache/ms-playwright` | idem : navigateurs de l'outil navigateur Hermes, réinstallés à la demande mais utiles si l'outil sert |
| 10 | `/tmp` | risque de casser un processus en cours pour 48 Mo |

Ces trois lignes restent disponibles sur un mot de vous (≈ 675 Mo).
