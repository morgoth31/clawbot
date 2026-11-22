# Déploiement P06 — validation du contrat du directeur en mode `warn`

**Date :** 2026-11-22 · **Branche :** `feat/REQ-ARCH-010-interfaces` · **Commit :** `4d64858`
**État du robot requis :** sur cales, aucune mission en cours. Indisponibilité : ~6 s
(redémarrage du seul directeur).

## Ce qui change

| Élément | Détail |
|---|---|
| Interfaces | 7 types ajoutés à `clawbot_interfaces` (`ExecuteSkill`, `ExecuteMission`, `ListCapabilities`, `SetCapability`, `GetMissionReport`, `SubmitDecision`, `MissionEvent`) — aucun n'est encore servi, donc aucun effet |
| Schémas | `clawbot_interfaces/schemas/director_command.schema.json`, `clawbot_common/share/clawbot_common/schemas/failure_report.schema.json`, `errors.json` |
| Directeur | paramètre `validation_mode` (`warn` par défaut) et contrôle à la frontière : journal `WARN` si la requête s'écarte du schéma, **traitement inchangé** |
| Écriture hors dépôt | aucune (`/etc` intact, pas de `daemon-reload`) |

## Journal

| Heure | Étape | Résultat |
|---|---|---|
| 16:02 | sauvegarde | `~/clawbot_backups/20261122-160225`, commit `4d64858` |
| 16:02 | vérification | `check.sh` 0 (585 passés) · `--integration` 0 (64 passés) |
| 16:02 | bascule | `systemctl restart clawbot-director`, 6 s ; directeur et sentinelle `active` |
| 16:02 | contrôles | voir ci-dessous |

## Contrôles

| Contrôle | Attendu | Mesuré |
|---|---|---|
| `ros2 param get /director validation_mode` | `warn` | `warn` |
| requête valide `{"op":"get_task"}` | traitée comme avant | `{"status": "FOUND", "task": {...}}` |
| `op` inconnu `{"op":"test_contrat"}` | `INVALID` + journal `WARN` | `{"status": "INVALID", "reason": "operation inconnue : 'test_contrat'"}` et `WARN contrat DirectorCommand : <racine>: … — reçu {"op": "test_contrat"}` |
| `start_skill` sans `skill` | `INVALID` + journal `WARN` | `{"status": "INVALID", "reason": "skill attendu"}` + `WARN` |
| unités | actives | `clawbot-director` et `clawbot-sentinel` `active` |

Aucune requête émise n'était une consigne de mouvement : seules `get_task` (lecture) et deux
requêtes invalides inoffensives ont été envoyées.

## Retour arrière

```bash
cd /home/jetson/clawbot
git checkout 994ec45
colcon build --packages-select clawbot_interfaces clawbot_common clawbot_director
sudo systemctl restart clawbot-director
```

Le mode `warn` n'ayant changé aucun comportement, le retour arrière n'est utile que pour retirer
les types et les schémas.

## Suite (hors P06)

Passage en `enforce` après 24 h de journal en `warn`, sur décision explicite de l'opérateur.
