# `bridge_mcp` — **obsolète** (remplacé par `clawbot_mcp`)

Ce paquet n'est plus le serveur MCP du robot. Depuis P10, le serveur exposé à Hermes est
**`clawbot_mcp`** (`clawbot_mcp/serveur.py`), une façade mince de l'exécutif de mission :
douze outils, aucun accès direct aux actionneurs (référentiel §9, REQ-MCP-001 à 007).

## Pourquoi il est conservé

Les trois appelants du directeur et plusieurs scripts d'exploitation importent encore des
modules d'ici (`bridge_mcp.director_client`, `bridge_mcp.health`, `bridge_mcp.notify`,
`bridge_mcp.hermes_trigger`). Le supprimer casserait ces appels avant que P14 ne les
rebranche. **Il sera supprimé en P14**, avec les scripts correspondants.

## Ce qui ne doit plus être utilisé

N'exposez plus ce paquet comme serveur MCP dans un profil Hermes : sa surface de commande
est plus large que celle du §9 (publication de paramètres, propositions de correctifs,
exécution de suites de tests, `safety_stop` distinct de `stop_robot`).

## Correspondance (25 outils → 12)

Voir `deploy/journal/2026-11-22_p10_rapport.md`, §« correspondance des 25 anciens outils ».
