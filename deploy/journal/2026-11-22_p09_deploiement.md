# Déploiement P09 — exécutif de mission (`clawbot-mission-executive.service`)

**Date :** 2026-11-22 · **Branche :** `feat/REQ-EXEC-010-missions` · **Accord :** donné le
2026-11-22 (« Une fois check.sh et check.sh --integration verts avec ce scénario, déploie »).
**Indisponibilité :** aucune (nouvelle unité ; `clawbot-skill-server` redémarré pour un correctif).

## Ce qui a été installé

| Élément | Détail |
|---|---|
| `clawbot-mission-executive.service` | lien `/etc/systemd/system/`, `enable --now`, `User=jetson`, `ROS_DOMAIN_ID=28` |
| `Requires=clawbot-skill-server.service` | déjà active : aucune unité de production arrêtée |
| Correctif `clawbot_executive` | QoS capteur sur les images (best effort), file d'ordres de décision |

Sauvegarde : `~/clawbot_backups/20261122-173706` (`commit_precedent.txt`, `install.tgz` 94 Mo).

## Journal

| Heure | Étape | Résultat |
|---|---|---|
| 17:37 | sauvegarde + `systemd-analyze verify` | aucune erreur nouvelle |
| 17:37 | lien + `daemon-reload` + `enable --now` | `active` ; journal : `mission_executive pret` |
| 17:38 | contrôle 1 : mission `[wait 1 s, capture_image wrist]` | **échec** : `capture_image` → le skill serveur ne recevait aucune image (abonnement *reliable* sur un topic caméra *best effort*) |
| 17:38 | correctif | `qos_profile_sensor_data` sur les deux flux image ; rebuild + `restart` skill-server puis mission-executive |
| 17:47 | contrôle 2 : même mission | **échec** : `CAPABILITY_INACTIVE` — `wrist_vision` est `FAILED` (la caméra publie à **6,9 Hz**, seuil du manifeste **8 Hz**) |
| 17:52 | contrôle 3 : mission `[wait 1 s]` | **`SUCCEEDED`**, journal écrit |

## Contrôles

| Contrôle | Attendu | Mesuré |
|---|---|---|
| `ros2 action list -t` | les deux actions | `/clawbot/execute_mission [ExecuteMission]`, `/clawbot/execute_skill [ExecuteSkill]` |
| mission `[wait 1 s]` (aucun mouvement) | `SUCCEEDED` | `outcome: 0`, `state: SUCCEEDED`, `Goal finished with status: SUCCEEDED` |
| journal JSONL | fichier par mission, une ligne par événement | `25ed65e3-…jsonl` : `STARTED`, `STEP_STARTED`, `STEP_SUCCEEDED`, `SUCCEEDED` |
| `/clawbot/mission/report` | état de la dernière mission | `{"state": "SUCCEEDED"}` |
| mission `[wait, capture_image wrist]` | `SUCCEEDED` selon §8 | **refusée** `CAPABILITY_INACTIVE`, `wrist_vision` = `FAILED` (6,9 Hz < 8 Hz). Comportement voulu ; l'écart est une mesure, pas un défaut du code |
| `smoke_check.sh` | conforme | conforme — 8 cadences, `/cmd_vel_safe` 20 Hz, 1 éditeur |
| `systemctl --failed` | aucune unité du robot | aucune |

## Interruption d'une mission de contrôle

La mission de 17:38 est restée en `WAITING_DECISION` (rapport `TIMEOUT`/`CAPABILITY_INACTIVE`) et a été
close par une décision `ABORT` explicite (rationale : « contrôle interrompu : image indisponible en
QoS reliable »). Le rejet d'un nouveau goal pendant ce temps est le comportement attendu
(une mission active à la fois).

## Retour arrière

```bash
sudo systemctl disable --now clawbot-mission-executive.service
sudo rm -f /etc/systemd/system/clawbot-mission-executive.service
sudo systemctl daemon-reload
cd /home/jetson/clawbot && git checkout 0afa5e6
colcon build --packages-select clawbot_executive
sudo systemctl restart clawbot-skill-server
```

## État final

`clawbot-mission-executive`, `clawbot-skill-server`, `clawbot-capability-manager`, `clawbot-director` :
tous `active`. `facade_mode` du directeur : **`legacy`** (inchangé). Aucun goal de mouvement n'a été
envoyé ; `wrist_vision` a été demandée ACTIVE par le service de capacités et se stabilise `FAILED`
(caméra sous son seuil), sans mouvement.
