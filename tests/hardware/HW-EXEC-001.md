# HW-EXEC-001 — Précision des skills de déplacement (`move_relative`, `rotate`)

**Exigence :** REQ-EXEC-007 · **Opérateur requis :** oui (essai matériel) · **Durée :** ~15 min
**Prérequis :** `clawbot-skill-server.service` active, `clawbot-capability-manager` active avec
`base` et `lidar` ACTIVE (`ros2 service call /clawbot/capabilities/list`).

## A. Sur cales — sécurité, annulation, e-stop

Robot sur cales, roues dans le vide, personne à moins d'un mètre des roues.

| Étape | Commande (terminal opérateur) | Attendu |
|---|---|---|
| A1 | `ros2 action send_goal /clawbot/execute_skill clawbot_interfaces/action/ExecuteSkill "{skill: move_relative, params_json: '{\"dx_m\": 0.3, \"max_speed_mps\": 0.1}'}" --feedback` | feedback `moving`, progression croissante, puis résultat `SUCCEEDED` (≈ 3 s de rotation) ; **aucun** `/cmd_vel_safe` non nul si l'e-stop est verrouillé |
| A2 | même commande, puis `Ctrl-C` sur le client ou `ros2 action cancel` | `CANCELED` en moins de 200 ms, consigne nulle publiée |
| A3 | même commande, puis appui sur l'e-stop pendant le mouvement | `FAILED`, `error_code: ESTOP_LATCHED`, consigne nulle, `failure_report_json` non vide |

**Ne pas réarmer l'e-stop sans avoir relu `/safety/state`** : le réarmement est un geste humain.

## B. Au sol — précision (REQ-EXEC-007)

Sol plan, espace dégagé de **2 m** devant le robot, opérateur présent, mètre ruban au sol, repère
tracé au ruban adhésif sur le point de départ du châssis.

| Étape | Commande | Mesure attendue |
|---|---|---|
| B1 | `move_relative {"dx_m": 0.5}` (max_speed par défaut 0,2 m/s) | distance au ruban : **0,50 m ± 0,05 m** |
| B2 | `move_relative {"dx_m": -0.5}` | retour : écart au point de départ **≤ 0,05 m** |
| B3 | `rotate {"angle_rad": 1.5708}` | angle au rapporteur / repère au sol : **90° ± 5°** |
| B4 | `rotate {"angle_rad": -1.5708}` | retour à l'orientation initiale ± 5° |

Consigner pour chaque étape : valeur demandée, valeur mesurée, écart, et le `result_json` renvoyé
par l'action. Les erreurs mesurées vont dans `deploy/journal/2026-11-22_p08_rapport.md` §« erreurs
mesurées ».

## C. Ce qui n'est pas couvert ici

`capture_image` (aucune caméra dans la boucle de test automatisée), `navigate_to` et `save_map`
(refusés avec `CAPABILITY_INACTIVE` tant que les capacités ne sont pas servies).
