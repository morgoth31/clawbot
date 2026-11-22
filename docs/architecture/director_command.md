# Contrat de `DirectorCommand` (façade du directeur)

**Version :** 1 · **Schéma :** `clawbot_interfaces/schemas/director_command.schema.json`
(draft 2020-12, un `oneOf` par `op`) · **Source du contrat :** `clawbot_director/director_node.py`

`DirectorCommand` reste un service à charge utile JSON (`request_json` / `response_json`) :
les trois appelants ne sont pas modifiables dans ce lot (C11). Ce document décrit ce que le
directeur accepte réellement, et le schéma le rend vérifiable.

## Opérations

| `op` | Paramètres | Effet | Réponse (champs stables) |
|---|---|---|---|
| `start_skill` | `skill` (chaîne non vide, requis), `args` (objet, défaut `{}`) | démarre un skill unique ; préconditions de sécurité et de bras vérifiées avant tout mouvement | `status` ∈ `ACCEPTED`, `BUSY`, `PRECONDITION_FAILED`, `INDISPONIBLE`, `INVALID` ; `task_id` si accepté |
| `start_sequence` | `steps` (liste non vide ; chaque étape `{skill, args?}`) | enchaîne 1 à N étapes, une seule en vol | comme `start_skill` |
| `get_task` | `task_id` (chaîne, optionnel) | état de la tâche ; sans `task_id`, la tâche courante | `status` ∈ `FOUND`, `UNKNOWN_TASK` ; `task` |
| `cancel_task` | `task_id` (optionnel), `reason` (optionnel, défaut `demande`) | annule au prochain point sûr | `status` ∈ `CANCELLED`, `NO_TASK`, `UNKNOWN_TASK` |
| `confirm` | `accepte` (booléen, requis) | répond à une demande de confirmation du directeur | `status` de reprise (`RUNNING` ou `CANCELLED`) |

Une opération inconnue répond aujourd'hui `{"status": "INVALID", "reason": "operation inconnue"}` ;
c'est ce comportement que le mode `warn` conserve.

## Validation à la frontière

Paramètre ROS `validation_mode` du nœud `director` :

- `warn` (**défaut**) — la requête est traitée exactement comme avant ; l'écart au schéma part en
  `WARN` dans le journal, avec le JSON reçu tronqué à 500 caractères.
- `enforce` — une requête invalide est refusée avant tout traitement :
  `{"ok": false, "error_code": "INVALID_PARAMS", "message": "<erreurs>"}`.

Le passage en `enforce` n'est pas fait dans P06 : il demande 24 h de journal en `warn` et une
décision explicite.

## Corpus

`clawbot_director/test/corpus/*.json` contient les requêtes réellement émises par les appelants,
chacune avec son origine (`appelant`) : pont MCP (`bridge_mcp/tools.py`), sentinelle
(`clawbot_sentinel/sentinel_node.py`), scripts d'exploitation (`scripts/brasd.py`,
`scripts/preuve_navigation_99.py`, `scripts/mesure_cadrage_poignet.py`). Trois fichiers
`invalide_*.json` fixent les refus attendus (sans `op`, `op` inconnu, paramètre de mauvais type).

## Écarts connus

- Le pont HTTP `:8000` relaie le JSON tel quel : il n'ajoute ni ne retire de champ, et n'a pas été
  modifié.
- Aucun appelant n'utilise `get_task` avec un `task_id` : le schéma l'autorise (le code le gère),
  le corpus ne l'exerce pas.
