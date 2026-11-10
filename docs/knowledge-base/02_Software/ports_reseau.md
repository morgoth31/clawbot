---
title: "Ports réseau du robot — allocation et résolution des conflits"
date: "2026-11-10T11:52:00+01:00"
author: "Hermes Agent"
tags: [software, reseau, ports, systemd, mkdocs, web_video_server, exploitation]
status: actif
---

# Ports réseau du robot — allocation et résolution des conflits

Relevé `sudo ss -ltnp` sur le poste, 2026-11-10 11:50 CET, `yahboom` (192.168.2.103 côté réseau local). Cette page fixe l'allocation : une nouvelle brique prend le premier port libre de la plage réservée, jamais un port déjà attribué ici. Retour à l'[[index]].

## 1. Ports effectivement en écoute

| Port | Service | Processus | Interface |
|---|---|---|---|
| 22 | SSH | `sshd` | toutes |
| 111 | rpcbind | `rpcbind` | toutes |
| 631 | CUPS | `cupsd` | toutes |
| 3389 | Bureau distant RDP | `gnome-remote-de` | toutes |
| 5900 | Bureau distant VNC | `gnome-remote-de` | toutes |
| 8000 | Pont LLM → ROS 2 (C++) | `api_server` | toutes |
| 8001 | Service matériel (Python) | `hardware_service` | toutes |
| 8003 | Service YOLO | `yolo_service.py` | toutes |
| 8080 | **Site de documentation** | `mkdocs` (`clawbot-docs.service`) | toutes |
| 8081 | Tableau de bord `charles_dashboard` | `python3 main.py` | toutes |
| 8888 | JupyterLab | `jupyter-lab` | toutes |
| 8889 | Conteneur Docker publié | `docker-proxy` | toutes |
| 9090 | rosbridge WebSocket | `rosbridge_websocket` | toutes |
| 11434 | Ollama | `ollama` | 127.0.0.1 |
| 11539 | Démon `ros2` (CLI) | `ros2-daemon` | 127.0.0.1 |

## 2. Conflit identifié : `web_video_server` contre le site de documentation

Le cours constructeur `11.Depth camera course/01.How to use the Astra camera` §1.4 lance `web_video_server` puis ouvre `http://<robot>:8080/`. Sur ce robot, **8080 est le site de documentation** : suivre le cours tel quel échoue (port occupé) ou, si le site est arrêté, prive l'exploitation de la base de connaissances.

Trois solutions, par ordre de préférence :

| Solution | Mise en œuvre | Conséquence |
|---|---|---|
| **1. Déplacer le flux vidéo sur 8082** (retenue) | `ros2 run web_video_server web_video_server --ros-args -p port:=8082` puis `http://<robot>:8082/` | aucun service existant touché ; le site reste sur 8080 |
| 2. Déplacer le site sur 8000 | modifier `clawbot-docs.service` (`--dev-addr 0.0.0.0:8000`) | casse les favoris, entre en conflit avec le pont C++ |
| 3. Servir la vidéo par le site | intégrer un `MJPEG` dans une page statique | dépendance supplémentaire, hors périmètre |

Le port 8082 est libre au relevé (`ss -ltn 'sport = :8082'` : aucune ligne). `web_video_server` n'est pas installé sur ce poste (`ros2 pkg list` ne renvoie que `image_transport` et ses transports) : la commande ci-dessus n'est valable qu'après `sudo apt install ros-humble-web-video-server`, à faire uniquement si le besoin de visualisation distante est confirmé.

## 3. Plage réservée

| Plage | Usage |
|---|---|
| 8000–8099 | services applicatifs du robot (ponts, tableaux de bord, documentation, vidéo) |
| 8888–8899 | notebooks et conteneurs publiés |
| 9090 | rosbridge |
| 11434 | Ollama (boucle locale uniquement) |

Nouvelle brique : prendre 8083, puis 8084, etc. Vérifier avec `sudo ss -ltn 'sport = :<port>'` **et** consigner la ligne dans le tableau §1 le jour du déploiement.

## 4. Vérification

```bash
sudo ss -ltnp | awk 'NR>1{split($4,a,":"); print a[length(a)]"\t"$6}' | sort -n
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/   # site de documentation
```

## 5. Voir aussi

- Caméra et cours constructeur qui documente `web_video_server` : [[orbbec_astra_pro_plus]]
- Unités systemd du robot : [[systemd_robot_services]]
- Pont LLM sur 8000/8001 : [[llm2ros_bridge]]
- Documentation constructeur : [[documentation_constructeur_yahboom]]
